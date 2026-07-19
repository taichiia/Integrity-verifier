import os

from PySide6.QtCore import QThread, Signal

from shared.hashing import hash_batch
from shared.checksum_file import read_csv, read_sfv


class VerifyWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(str, int, str, int)
    finished = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, checksum_entries: list[dict], target_dir: str,
                 algorithm: str = "sha256", parent=None):
        super().__init__(parent)
        self._entries = checksum_entries
        self._target_dir = target_dir
        self._algorithm = algorithm
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            report = {
                "total": len(self._entries),
                "passed": 0,
                "failed": 0,
                "missing": 0,
                "extra": [],
                "details": [],
            }

            paths_to_check = []
            for entry in self._entries:
                full = os.path.join(self._target_dir, entry["path"])
                paths_to_check.append((entry["path"], full, entry.get("hash", "")))

            manifest_paths = set(e["path"].replace("\\", "/").lower()
                                 for e in self._entries)
            try:
                for root, _, files in os.walk(self._target_dir):
                    if self._cancelled:
                        break
                    for f in files:
                        full = os.path.join(root, f)
                        try:
                            rel = os.path.relpath(full, self._target_dir).replace("\\", "/")
                        except ValueError:
                            rel = full
                        if rel.lower() not in manifest_paths:
                            report["extra"].append(rel)
                            report["details"].append({
                                "path": rel,
                                "status": "extra",
                                "expected": "",
                                "actual": "",
                            })
            except OSError:
                pass
            report["extra_count"] = len(report["extra"])

            for i, (rel_path, full_path, expected_hash) in enumerate(paths_to_check):
                if self._cancelled:
                    break

                self.progress.emit(i + 1, len(paths_to_check), rel_path)

                if not os.path.isfile(full_path):
                    report["missing"] += 1
                    report["details"].append({
                        "path": rel_path,
                        "status": "missing",
                        "expected": expected_hash,
                        "actual": "",
                    })
                    self.result.emit(rel_path, i, "missing", len(paths_to_check))
                    continue

                try:
                    from shared.hashing import hash_file
                    actual = hash_file(full_path, self._algorithm)
                except Exception as e:
                    report["failed"] += 1
                    report["details"].append({
                        "path": rel_path,
                        "status": "error",
                        "expected": expected_hash,
                        "actual": str(e),
                    })
                    self.result.emit(rel_path, i, "error", len(paths_to_check))
                    continue

                if actual == expected_hash:
                    report["passed"] += 1
                    report["details"].append({
                        "path": rel_path,
                        "status": "pass",
                        "expected": expected_hash,
                        "actual": actual,
                    })
                    self.result.emit(rel_path, i, "pass", len(paths_to_check))
                else:
                    report["failed"] += 1
                    report["details"].append({
                        "path": rel_path,
                        "status": "fail",
                        "expected": expected_hash,
                        "actual": actual,
                    })
                    self.result.emit(rel_path, i, "fail", len(paths_to_check))

            self.finished.emit(report)

        except Exception as e:
            self.error_occurred.emit(str(e))

