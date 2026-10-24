import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, Signal
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QMenu, QAbstractItemView, QFileDialog,
)
from shared.constants import FONT_BODY_SIZE
from shared.theme import get_palette


def path_key(path: str) -> str:
    """Case-insensitive identity used to keep one row per real file."""
    try:
        if os.path.isabs(path):
            # abspath() calls getcwd() on every invocation; a scan of 200k
            # files would otherwise pay that syscall for every row.
            return os.path.normcase(os.path.normpath(path))
        return os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        return os.path.normcase(path)


def dedupe_key(entry: dict) -> str:
    """Return the caller's precomputed path identity when available."""
    key = entry.get("_identity_key")
    if isinstance(key, str) and key:
        return key
    return path_key(entry["path"])


def format_modified(value) -> str:
    """Render a stored mtime (float seconds or pre-formatted text)."""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return ""
    return str(value)[:19]


class FileTableModel(QAbstractTableModel):
    COL_CHECKED = 0
    COL_PATH = 1
    COL_SIZE = 2
    COL_MODIFIED = 3

    HEADERS = ["", "文件路径", "大小", "修改时间"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list[dict] = []
        self._keys: set[str] = set()
        self._checked = 0

    def rowCount(self, parent=QModelIndex()):
        return len(self._files)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._files[index.row()]

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.COL_CHECKED:
            return Qt.CheckState.Checked if row["checked"] else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == self.COL_PATH:
                return row["path"]
            elif col == self.COL_SIZE:
                return self._format_size(row["size"])
            elif col == self.COL_MODIFIED:
                return format_modified(row.get("mtime", row.get("modified", "")))

        if role == Qt.ItemDataRole.ToolTipRole:
            return row["path"]

        if role == Qt.ItemDataRole.DecorationRole and index.column() == self.COL_PATH:
            ext = Path(row["path"]).suffix.lower()
            if ext in (".exe", ".dll", ".pyd"):
                return None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.COL_CHECKED:
            state = value if isinstance(value, Qt.CheckState) else Qt.CheckState(value)
            row = self._files[index.row()]
            checked = (state == Qt.CheckState.Checked)
            if row["checked"] != checked:
                row["checked"] = checked
                self._checked += 1 if checked else -1
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_CHECKED:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def add_files(self, entries: list[dict]):
        if not entries:
            return 0
        fresh = []
        for entry in entries:
            key = dedupe_key(entry)
            if key in self._keys:
                continue
            self._keys.add(key)
            fresh.append(entry)
        if not fresh:
            return 0
        start = len(self._files)
        self.beginInsertRows(QModelIndex(), start, start + len(fresh) - 1)
        for entry in fresh:
            entry.setdefault("checked", True)
            self._files.append(entry)
            if entry["checked"]:
                self._checked += 1
        self.endInsertRows()
        return len(fresh)

    def set_files(self, entries: list[dict]):
        if len(entries) == len(self._files) and all(
            old is new for old, new in zip(self._files, entries)
        ):
            return 0

        self.beginResetModel()
        self._files = []
        self._keys = set()
        self._checked = 0
        for entry in entries:
            key = dedupe_key(entry)
            if key in self._keys:
                continue
            self._keys.add(key)
            entry.setdefault("checked", True)
            self._files.append(entry)
            if entry["checked"]:
                self._checked += 1
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._files = []
        self._keys.clear()
        self._checked = 0
        self.endResetModel()

    def get_checked(self) -> list[dict]:
        return [f for f in self._files if f["checked"]]

    def get_all(self) -> list[dict]:
        return list(self._files)

    def checked_count(self) -> int:
        """O(1): the scan path updates the selection state thousands of times."""
        return self._checked

    def remove_rows(self, indices: list[int]):
        rows = sorted(set(indices), reverse=True)
        start = None
        previous = None
        for row in rows:
            if start is None:
                start = row
            elif row != previous - 1:
                self._remove_range(min(start, previous), max(start, previous))
                start = row
            previous = row
        if start is not None:
            self._remove_range(min(start, previous), max(start, previous))

    def _remove_range(self, first: int, last: int):
        if last < first:
            return
        self.beginRemoveRows(QModelIndex(), first, last)
        for row in range(last, first - 1, -1):
            entry = self._files[row]
            if entry["checked"]:
                self._checked -= 1
            del self._files[row]
            self._keys.discard(dedupe_key(entry))
        self.endRemoveRows()

    def base_directory(self) -> str:
        if not self._files:
            return ""
        paths = [f["path"] for f in self._files]
        return os.path.commonpath(paths) if paths else ""

    def select_all(self):
        for f in self._files:
            f["checked"] = True
        self._checked = len(self._files)
        self._emit_check_state_changes()

    def select_none(self):
        for f in self._files:
            f["checked"] = False
        self._checked = 0
        self._emit_check_state_changes()

    def invert_selection(self):
        for f in self._files:
            f["checked"] = not f["checked"]
        self._checked = len(self._files) - self._checked
        self._emit_check_state_changes()

    def _emit_check_state_changes(self):
        if not self._files:
            return
        first = self.index(0, self.COL_CHECKED)
        last = self.index(len(self._files) - 1, self.COL_CHECKED)
        self.dataChanged.emit(first, last, [Qt.ItemDataRole.CheckStateRole])

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


class FileTableView(QTableView):
    files_dropped = Signal(list)
    files_added = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = FileTableModel()
        self.setModel(self._model)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(self._model.COL_CHECKED, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(self._model.COL_CHECKED, 36)
        hh.setSectionResizeMode(self._model.COL_PATH, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(self._model.COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(self._model.COL_MODIFIED, QHeaderView.ResizeMode.ResizeToContents)

        vh = self.verticalHeader()
        vh.setVisible(False)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._scanning = False
        self._scan_frame = 0
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(500)
        self._scan_timer.timeout.connect(self._update_scan_animation)
        self._refresh_empty_state_accessibility()

    def model(self) -> FileTableModel:
        return self._model

    def set_scanning(self, scanning: bool):
        self._scanning = scanning
        if scanning:
            self._scan_frame = 0
            self._scan_timer.start()
        else:
            self._scan_timer.stop()
        self._refresh_empty_state_accessibility()
        self.viewport().update()

    def _update_scan_animation(self):
        self._scan_frame = (self._scan_frame + 1) % 4
        self.viewport().update()

    def _refresh_empty_state_accessibility(self):
        if self._scanning:
            self.setAccessibleName("正在扫描文件列表")
            self.setAccessibleDescription("正在收集文件路径和元数据，完成后会显示文件列表")
        else:
            self.setAccessibleName("文件列表")
            self.setAccessibleDescription("选择源文件夹或拖拽文件后，这里会显示待校验文件")

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._model.rowCount() == 0:
            pal = get_palette()
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.viewport().rect()
            font = QFont(self.font())
            font.setPointSize(FONT_BODY_SIZE + 1)
            painter.setFont(font)
            painter.setPen(QColor(pal["secondary"]))
            if self._scanning:
                title = "正在扫描文件" + "." * self._scan_frame
                hint = "正在收集路径和元数据，完成后会自动显示列表"
            else:
                title = "尚未选择源文件夹"
                hint = "点击上方「浏览...」选择目录，或直接拖拽文件到此处"
            painter.drawText(
                rect.adjusted(0, -20, 0, -20),
                Qt.AlignmentFlag.AlignCenter,
                title,
            )
            hint_font = QFont(self.font())
            hint_font.setPointSize(FONT_BODY_SIZE - 1)
            painter.setFont(hint_font)
            painter.setPen(QColor(pal["border"]))
            painter.drawText(
                rect.adjusted(0, 16, 0, 16),
                Qt.AlignmentFlag.AlignCenter,
                hint,
            )
            painter.end()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        paths.append(os.path.join(root, f))
            elif os.path.isfile(p):
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        remove_action = QAction("移除选中文件", self)
        remove_action.setToolTip("将选中的文件从清单中移除")
        remove_action.triggered.connect(self._remove_selected)
        menu.addAction(remove_action)

        add_action = QAction("添加外部文件...", self)
        add_action.setToolTip("添加不在当前目录中的外部文件到清单")
        add_action.triggered.connect(self._add_external)
        menu.addAction(add_action)

        menu.addSeparator()

        explorer_action = QAction("在资源管理器中打开", self)
        explorer_action.setToolTip("打开文件所在文件夹并定位到该文件")
        explorer_action.triggered.connect(self._open_in_explorer)
        menu.addAction(explorer_action)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _remove_selected(self):
        rows = sorted(set(i.row() for i in self.selectedIndexes()), reverse=True)
        self._model.remove_rows(rows)

    def _add_external(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add External Files")
        if paths:
            entries = []
            for p in paths:
                try:
                    stat = os.stat(p)
                    entries.append({
                        "path": p,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "checked": True,
                    })
                except OSError:
                    pass
            self._model.add_files(entries)
            if entries:
                self.files_added.emit(entries)

    def _open_in_explorer(self):
        for idx in self.selectedIndexes():
            if idx.column() == self._model.COL_PATH:
                path = self._model._files[idx.row()]["path"]
                import subprocess
                subprocess.Popen(["explorer", f"/select,{path}"])
                break

