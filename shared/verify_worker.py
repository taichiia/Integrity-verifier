from PySide6.QtCore import QThread, Signal

from shared.verification import run_verification


class _CancelFlag:
    """Adapter so shared.hashing can observe the worker's cancel flag."""

    def __init__(self, worker: "VerifyWorker"):
        self._worker = worker

    def is_set(self) -> bool:
        return self._worker._cancelled


class VerifyWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(str, int, str, int)
    # Deliberately *not* named ``finished``: QThread already defines that
    # signal, and shadowing it made the no-argument QThread.finished emission
    # call slots that require the report dict.
    completed = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, checksum_entries: list[dict], target_dir: str,
                 algorithm: str = "sha256", parent=None,
                 exclude_paths: list[str] | None = None,
                 exclude_rules=None,
                 ignored_paths: list[str] | None = None):
        super().__init__(parent)
        self._entries = checksum_entries
        self._target_dir = target_dir
        self._algorithm = algorithm
        self._cancelled = False
        self._cancel_flag = _CancelFlag(self)
        self._exclude_paths = list(exclude_paths or [])
        self._exclude_rules = exclude_rules
        self._ignored_paths = list(ignored_paths or [])

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            report = run_verification(
                self._entries,
                self._target_dir,
                self._algorithm,
                cancel_event=self._cancel_flag,
                progress_callback=self.progress.emit,
                result_callback=self.result.emit,
                exclude_paths=self._exclude_paths,
                exclude_rules=self._exclude_rules,
                ignored_paths=self._ignored_paths,
            )
            self.completed.emit(report)
        except Exception as e:
            self.error_occurred.emit(str(e))
