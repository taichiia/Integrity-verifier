import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from PySide6.QtCore import QThread, Signal

from shared.hashing import HashCancelled, default_workers, hash_file


_CANCELLED = "__cancelled__"


class HashWorker(QThread):
    BATCH_SIZE = 256
    FLUSH_INTERVAL_SECONDS = 0.016

    progress = Signal(int, int, str)
    speed = Signal(float)
    file_done = Signal(str, str, str)
    files_done = Signal(list)
    completed = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        file_paths: list[str],
        algorithm: str = "sha256",
        max_workers: int | None = None,
        batch_size: int = 64,
        parent=None,
    ):
        super().__init__(parent)
        self._paths = file_paths
        self._algorithm = algorithm
        self._max_workers = max_workers or default_workers()
        self._pending_limit = max(1, self._max_workers * 4, batch_size)
        self._paused = False
        self._cancelled = False
        self._cancel_event = threading.Event()

    def pause(self):
        self._paused = True

    def resume_worker(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True
        self._cancel_event.set()

    def run(self):
        total = len(self._paths)
        results = []
        completed = 0
        batch: list[tuple[str, str, str]] = []
        last_flush = time.perf_counter()
        start_time = time.perf_counter()

        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                path_iterator = iter(self._paths)
                pending: dict[Future, str] = {}

                def submit_more():
                    while (
                        len(pending) < self._pending_limit
                        and not self._cancelled
                    ):
                        try:
                            path = next(path_iterator)
                        except StopIteration:
                            return
                        pending[executor.submit(
                            _safe_hash,
                            path,
                            self._algorithm,
                            self._cancel_event,
                        )] = path

                def flush_batch():
                    nonlocal completed, last_flush
                    if not batch:
                        return
                    results.extend(batch)
                    completed += len(batch)
                    self.files_done.emit(batch.copy())
                    self.progress.emit(completed, total, batch[-1][0])
                    elapsed = time.perf_counter() - start_time
                    if elapsed > 0.5:
                        self.speed.emit(completed / elapsed)
                    batch.clear()
                    last_flush = time.perf_counter()

                submit_more()
                while pending:
                    if self._cancelled:
                        for future in pending:
                            future.cancel()
                        break

                    while self._paused and not self._cancelled:
                        self.msleep(100)

                    if self._cancelled:
                        for future in pending:
                            future.cancel()
                        break

                    done, _ = wait(
                        pending,
                        timeout=0.1,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done:
                        continue

                    for future in done:
                        path = pending.pop(future)
                        try:
                            digest, error = future.result()
                        except HashCancelled:
                            continue
                        except Exception as exc:
                            digest, error = "", str(exc)

                        if error == _CANCELLED:
                            continue

                        batch.append((path, digest, error))
                        if (len(batch) >= self.BATCH_SIZE
                                or time.perf_counter() - last_flush
                                >= self.FLUSH_INTERVAL_SECONDS):
                            flush_batch()

                    submit_more()

        except Exception as e:
            self.error_occurred.emit(str(e))

        flush_batch()
        self.completed.emit(results)


def _safe_hash(
    filepath: str,
    algorithm: str,
    cancel_event: threading.Event | None = None,
) -> tuple[str, str]:
    try:
        return hash_file(filepath, algorithm, cancel_event=cancel_event), ""
    except HashCancelled:
        return "", _CANCELLED
    except PermissionError:
        return "", "Permission denied"
    except FileNotFoundError:
        return "", "File not found"
    except OSError as e:
        return "", str(e)
    except Exception as e:
        return "", f"Unexpected: {e}"
