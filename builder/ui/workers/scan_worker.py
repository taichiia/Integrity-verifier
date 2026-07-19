import os
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QThread, Signal


class ScanWorker(QThread):
    progress = Signal(int, int)
    file_found = Signal(str, int, str)
    scan_complete = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, directories: list[str],
                 filter_extensions: list[str] | None = None,
                 filter_folders: list[str] | None = None,
                 filter_blacklist: bool = True,
                 filter_min_size: int = 0,
                 filter_max_size: int = 0,
                 parent=None):
        super().__init__(parent)
        self._dirs = directories
        self._exts = set(e.lower().lstrip(".") for e in (filter_extensions or []))
        self._folders = set(f.lower() for f in (filter_folders or []))
        self._blacklist = filter_blacklist
        self._min_size = filter_min_size
        self._max_size = filter_max_size
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            all_files = []
            for directory in self._dirs:
                if self._cancelled:
                    break
                self._collect(directory, all_files)

            total = len(all_files)
            for i, filepath in enumerate(all_files):
                if self._cancelled:
                    break
                try:
                    stat = os.stat(filepath)
                    size = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    self.file_found.emit(filepath, size, mtime)
                    self.progress.emit(i + 1, total)
                except OSError:
                    continue

            self.scan_complete.emit(total)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _collect(self, directory: str, result: list):
        try:
            for entry in os.scandir(directory):
                if self._cancelled:
                    return
                if entry.is_dir(follow_symlinks=False):
                    if self._matches_folder_filter(entry.name):
                        self._collect(entry.path, result)
                elif entry.is_file(follow_symlinks=False):
                    if self._matches_filter(entry.path, entry.name):
                        result.append(entry.path)
        except PermissionError:
            self.error_occurred.emit(f"Permission denied: {directory}")
        except OSError as e:
            self.error_occurred.emit(f"Scan error in {directory}: {e}")

    def _matches_filter(self, full_path: str, name: str) -> bool:
        try:
            size = os.path.getsize(full_path)
        except OSError:
            return False
        if self._min_size > 0 and size < self._min_size:
            return False
        if self._max_size > 0 and size > self._max_size:
            return False

        if not self._exts:
            return True
        ext = Path(name).suffix.lower().lstrip(".")
        if ext in self._exts:
            return not self._blacklist
        return self._blacklist

    def _matches_folder_filter(self, name: str) -> bool:
        if not self._folders:
            return True
        if name.lower() in self._folders:
            return not self._blacklist
        return self._blacklist

