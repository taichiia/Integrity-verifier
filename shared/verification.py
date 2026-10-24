"""Qt-free target verification used by CLI and GUI worker wrappers."""

import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from shared.file_rules import FileRules
from shared.hashing import HashCancelled, default_workers, hash_file


def normalize_manifest_path(path: str) -> str:
    return os.path.normpath(
        str(path).replace("\\", "/")
    ).replace("\\", "/").lower()


def run_verification(
    checksum_entries: list[dict],
    target_dir: str,
    algorithm: str = "sha256",
    cancel_event=None,
    progress_callback=None,
    result_callback=None,
    exclude_paths: list[str] | None = None,
    exclude_rules: "FileRules | dict | None" = None,
    ignored_paths: list[str] | None = None,
) -> dict:
    rules = FileRules.from_config(exclude_rules)
    absolute_excludes = {
        os.path.normcase(os.path.abspath(path))
        for path in (exclude_paths or [])
        if str(path).strip()
    }
    ignored = {
        normalize_manifest_path(path)
        for path in (ignored_paths or [])
        if str(path).strip()
    }
    report = {
        "total": len(checksum_entries),
        "passed": 0,
        "failed": 0,
        "missing": 0,
        "extra": [],
        "errors": [],
        "details": [],
    }

    paths_to_check = []
    for entry in checksum_entries:
        full = os.path.join(target_dir, entry["path"])
        paths_to_check.append((entry["path"], full, entry.get("hash", "")))

    _collect_extras(
        report,
        checksum_entries,
        target_dir,
        rules,
        absolute_excludes,
        ignored,
        cancel_event,
    )
    report["extra_count"] = len(report["extra"])

    details = [None] * len(paths_to_check)

    existing_paths: dict[str, list[tuple[int, str, str]]] = {}
    for index, (rel_path, full_path, expected_hash) in enumerate(paths_to_check):
        if not os.path.isfile(full_path):
            report["missing"] += 1
            details[index] = {
                "path": rel_path,
                "status": "missing",
                "expected": expected_hash,
                "actual": "",
            }
            if progress_callback is not None:
                progress_callback(index + 1, len(paths_to_check), rel_path)
            if result_callback is not None:
                result_callback(rel_path, index, "missing", len(paths_to_check))
        else:
            existing_paths.setdefault(full_path, []).append(
                (index, rel_path, expected_hash)
            )
    _verify_files(
        list(existing_paths),
        algorithm,
        cancel_event,
        report,
        existing_paths,
        details,
        len(paths_to_check),
        progress_callback,
        result_callback,
    )

    report["details"].extend(detail for detail in details if detail is not None)

    return report


def _verify_files(
    paths: list[str],
    algorithm: str,
    cancel_event,
    report: dict,
    path_infos: dict[str, list[tuple[int, str, str]]],
    details: list[dict | None],
    total: int,
    progress_callback,
    result_callback,
) -> None:
    if not paths:
        return

    max_workers = default_workers()
    pending_limit = max(1, max_workers * 4)
    completed = sum(detail is not None for detail in details)
    path_iterator = iter(paths)
    pending: dict[Future, str] = {}

    def on_result(full_path: str, digest: str, error: str) -> None:
        nonlocal completed
        for index, rel_path, expected_hash in path_infos[full_path]:
            status = "error" if error else ("pass" if digest == expected_hash else "fail")
            if status == "pass":
                report["passed"] += 1
            else:
                report["failed"] += 1
            details[index] = {
                "path": rel_path,
                "status": status,
                "expected": expected_hash,
                "actual": "" if error else digest,
            }
            if result_callback is not None:
                result_callback(rel_path, index, status, total)

        completed += 1
        if progress_callback is not None:
            progress_callback(completed, total, rel_path)

    def cancel_pending() -> None:
        for future in pending:
            future.cancel()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while len(pending) < pending_limit:
            try:
                path = next(path_iterator)
            except StopIteration:
                break
            pending[executor.submit(
                _hash_file_for_verification, path, algorithm, cancel_event,
            )] = path

        while pending:
            if cancel_event is not None and cancel_event.is_set():
                cancel_pending()
                break

            done, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            if not done:
                continue

            for future in done:
                full_path = pending.pop(future)
                try:
                    digest, error = future.result()
                except HashCancelled:
                    continue
                except Exception as exc:
                    digest, error = "", str(exc)
                on_result(full_path, digest, error)

            while len(pending) < pending_limit:
                try:
                    path = next(path_iterator)
                except StopIteration:
                    break
                pending[executor.submit(
                    _hash_file_for_verification, path, algorithm, cancel_event,
                )] = path


def _hash_file_for_verification(
    full_path: str,
    algorithm: str,
    cancel_event,
) -> tuple[str, str]:
    try:
        return hash_file(full_path, algorithm, cancel_event=cancel_event), ""
    except HashCancelled:
        raise
    except Exception as exc:
        return "", str(exc)


def _collect_extras(
    report: dict,
    checksum_entries: list[dict],
    target_dir: str,
    rules: FileRules,
    absolute_excludes: set[str],
    ignored: set[str],
    cancel_event,
):
    manifest_paths = {
        normalize_manifest_path(entry["path"])
        for entry in checksum_entries
    }

    def on_walk_error(error: OSError):
        report["errors"].append(str(error))

    # followlinks=False matches the Builder scanner: a directory symlink is
    # not followed, while a symlinked file is treated like a normal file.
    for root, dirs, files in os.walk(
        target_dir, onerror=on_walk_error, followlinks=False,
    ):
        if cancel_event is not None and cancel_event.is_set():
            break
        dirs.sort()
        files.sort()
        if absolute_excludes:
            dirs[:] = [
                directory for directory in dirs
                if os.path.normcase(os.path.abspath(os.path.join(root, directory)))
                not in absolute_excludes
            ]
        if rules.enabled and rules.blacklist:
            dirs[:] = [
                directory for directory in dirs
                if not rules.excludes_directory(directory)
            ]

        for filename in files:
            # A verifier beside the target files must not count itself.
            if (root == target_dir
                    and filename.lower() == "fileintegrityverifier.exe"):
                continue
            full = os.path.join(root, filename)
            if (absolute_excludes
                    and os.path.normcase(os.path.abspath(full)) in absolute_excludes):
                continue
            try:
                rel = os.path.relpath(full, target_dir).replace("\\", "/")
            except ValueError:
                rel = full
            if normalize_manifest_path(rel) in ignored:
                # Explicitly unchecked/removed Builder files are not unexpected.
                continue
            if rel.lower() in manifest_paths:
                continue
            if rules.enabled and rules.excludes(rel, _safe_size(full)):
                # The Builder deliberately keeps ignored files out of the
                # manifest; they must not be reported as extra.
                continue
            report["extra"].append(rel)
            report["details"].append({
                "path": rel,
                "status": "extra",
                "expected": "",
                "actual": "",
            })


def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
