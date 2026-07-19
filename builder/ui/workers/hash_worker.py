import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

from PySide6.QtCore import QThread, Signal

from shared.hashing import hash_file


class HashWorker(QThread):
    progress = Signal(int, int, str)
    speed = Signal(float)
    file_done = Signal(str, str, str)
    finished = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, file_paths: list[str], algorithm: str = "sha256",
                 max_workers: int | None = None, batch_size: int = 64,
                 parent=None):
        super().__init__(parent)
        self._paths = file_paths
        self._algorithm = algorithm
        self._max_workers = max_workers or max(1, (os.cpu_count() or 4) - 1)
        self._batch_size = batch_size
        self._paused = False
        self._cancelled = False

    def pause(self):
        self._paused = True

    def resume_worker(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self._paths)
        results = []
        completed = 0
        start_time = time.perf_counter()

        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                future_map: dict[Future, str] = {}
                for path in self._paths:
                    if self._cancelled:
                        break
                    future = executor.submit(_safe_hash, path, self._algorithm)
                    future_map[future] = path

                for future in as_completed(future_map):
                    while self._paused and not self._cancelled:
                        self.msleep(100)

                    if self._cancelled:
                        for f in future_map:
                            f.cancel()
                        break

                    path = future_map[future]
                    try:
                        digest, error = future.result()
                    except Exception as exc:
                        digest, error = "", str(exc)

                    results.append((path, digest, error))
                    completed += 1

                    self.file_done.emit(path, digest, error)
                    self.progress.emit(completed, total, path)

                    elapsed = time.perf_counter() - start_time
                    if elapsed > 0.5:
                        self.speed.emit(completed / elapsed)

        except Exception as e:
            self.error_occurred.emit(str(e))

        self.finished.emit(results)


def _safe_hash(filepath: str, algorithm: str) -> tuple[str, str]:
    try:
        return hash_file(filepath, algorithm), ""
    except PermissionError:
        return "", "Permission denied"
    except FileNotFoundError:
        return "", "File not found"
    except OSError as e:
        return "", str(e)
    except Exception as e:
        return "", f"Unexpected: {e}"

