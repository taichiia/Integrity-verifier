import hashlib
import os
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Iterator


READ_CHUNK = 4 * 1024 * 1024
SMALL_FILE_LIMIT = 1024 * 1024
MAX_WORKERS = 4
PENDING_PER_WORKER = 4
_thread_local = threading.local()


class HashCancelled(Exception):
    """Raised when a large-file hash is cancelled between read chunks."""


def default_workers() -> int:
    return max(1, min(MAX_WORKERS, os.cpu_count() or MAX_WORKERS))


def hash_file(
    filepath: str,
    algorithm: str = "sha256",
    cancel_event=None,
) -> str:
    h = hashlib.new(algorithm)

    with open(filepath, "rb") as f:
        if cancel_event is not None and cancel_event.is_set():
            raise HashCancelled()

        # Small files dominate scans with thousands of entries.  Allocating a
        # fresh 4 MiB buffer for each one wastes time and memory bandwidth.
        size = os.fstat(f.fileno()).st_size
        if size <= SMALL_FILE_LIMIT:
            data = f.read(SMALL_FILE_LIMIT + 1)
            if cancel_event is not None and cancel_event.is_set():
                raise HashCancelled()
            h.update(data)
            if len(data) <= SMALL_FILE_LIMIT:
                return h.hexdigest()

        buffer = getattr(_thread_local, "buffer", None)
        if buffer is None or len(buffer) != READ_CHUNK:
            buffer = bytearray(READ_CHUNK)
            _thread_local.buffer = buffer
        view = memoryview(buffer)

        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise HashCancelled()

            read_count = f.readinto(view)
            if not read_count:
                break
            h.update(view[:read_count])

    return h.hexdigest()


def hash_batch(
    paths: list[str],
    algorithm: str = "sha256",
    max_workers: int | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[tuple[str, str, str | None]]:
    results: dict[str, tuple[str, str | None]] = {}
    for completed, (path, digest, error) in enumerate(
        hash_generator(paths, algorithm, max_workers),
        start=1,
    ):
        results[path] = (digest, error)
        if progress_callback:
            progress_callback(completed, len(paths), path)

    return [(p, results[p][0], results[p][1]) for p in paths]


def hash_generator(
    paths: list[str],
    algorithm: str = "sha256",
    max_workers: int | None = None,
) -> Iterator[tuple[str, str, str | None]]:
    if max_workers is None:
        max_workers = default_workers()

    pending_limit = max(max_workers, max_workers * PENDING_PER_WORKER)
    path_iterator = iter(paths)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending = {}

        def submit_more():
            while len(pending) < pending_limit:
                try:
                    path = next(path_iterator)
                except StopIteration:
                    return
                pending[executor.submit(_hash_single, path, algorithm)] = path

        submit_more()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                path = pending.pop(future)
                try:
                    digest, error = future.result()
                except Exception as exc:
                    digest, error = "", str(exc)
                yield path, digest, error
            submit_more()


def _hash_single(
    filepath: str,
    algorithm: str,
    cancel_event=None,
) -> tuple[str, str | None]:
    try:
        return hash_file(filepath, algorithm, cancel_event=cancel_event), None
    except HashCancelled:
        raise
    except PermissionError:
        return "", "Permission denied"
    except FileNotFoundError:
        return "", "File not found"
    except OSError as e:
        return "", str(e)
    except Exception as e:
        return "", f"Unexpected: {e}"
