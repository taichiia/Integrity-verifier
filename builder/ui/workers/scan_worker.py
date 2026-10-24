import os

from PySide6.QtCore import QThread, Signal


class ScanWorker(QThread):
    """Collect every file under the given directories.

    Filtering is deliberately *not* done here.  Step 1 keeps the full file
    list so that changing or disabling a filter can bring previously hidden
    files back, and so the manifest never disagrees with the verifier about
    which files live inside the target folder.
    """

    BATCH_SIZE = 512

    progress = Signal(int, int)
    # Batched on purpose: one queued signal per file made the UI thread the
    # bottleneck (20k files: 0.4 s of walking, ~7 min of per-file updates).
    files_found = Signal(list)
    scan_complete = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(self, directories: list[str], parent=None):
        super().__init__(parent)
        self._dirs = list(directories)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            collected: list[tuple[str, int, float]] = []
            skipped = 0
            emitted = 0

            def flush_batch():
                nonlocal emitted
                if not collected:
                    return
                emitted += len(collected)
                self.files_found.emit(collected.copy())
                collected.clear()

            for directory in self._dirs:
                if self._cancelled:
                    break
                skipped += self._collect(directory, collected, flush_batch)
            flush_batch()

            total = emitted
            self.progress.emit(total, total)

            self.scan_complete.emit(total, skipped)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _collect(
        self,
        directory: str,
        result: list[tuple[str, int, float]],
        flush_batch,
    ) -> int:
        """Append ``(path, size, mtime)`` tuples and return the skip count."""
        skipped = 0
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
        except PermissionError:
            self.error_occurred.emit(f"Permission denied: {directory}")
            return 1
        except OSError as e:
            self.error_occurred.emit(f"Scan error in {directory}: {e}")
            return 1

        for entry in entries:
            if self._cancelled:
                return skipped
            try:
                if entry.is_dir(follow_symlinks=False):
                    skipped += self._collect(entry.path, result, flush_batch)
                elif entry.is_file():
                    # Only the metadata matters here; the file content is hashed
                    # later so a large tree never has to be read twice.
                    stat = entry.stat()
                    # The timestamp stays a float; formatting 20k of them is
                    # wasted work when only the visible rows are ever drawn.
                    result.append((entry.path, stat.st_size, stat.st_mtime))
                    if len(result) >= self.BATCH_SIZE:
                        flush_batch()
            except OSError as e:
                # A file that disappears or cannot be stat'ed mid-scan must be
                # reported, otherwise the manifest silently loses an entry.
                skipped += 1
                self.error_occurred.emit(f"Skipped {entry.path}: {e}")
        return skipped

