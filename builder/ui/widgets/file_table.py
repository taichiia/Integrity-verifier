import os
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QMenu, QAbstractItemView, QFileDialog,
)


class FileTableModel(QAbstractTableModel):
    COL_CHECKED = 0
    COL_PATH = 1
    COL_SIZE = 2
    COL_MODIFIED = 3

    HEADERS = ["", "文件路径", "大小", "修改时间"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list[dict] = []

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
                return row.get("modified", "")[:19]

        if role == Qt.ItemDataRole.ToolTipRole:
            return row["path"]

        if role == Qt.ItemDataRole.DecorationRole and index.column() == self.COL_PATH:
            ext = Path(row["path"]).suffix.lower()
            if ext in (".exe", ".dll", ".pyd"):
                return None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.COL_CHECKED:
            self._files[index.row()]["checked"] = (value == Qt.CheckState.Checked.value)
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
            return
        start = len(self._files)
        self.beginInsertRows(QModelIndex(), start, start + len(entries) - 1)
        for entry in entries:
            entry.setdefault("checked", True)
            self._files.append(entry)
        self.endInsertRows()

    def set_files(self, entries: list[dict]):
        self.beginResetModel()
        self._files = []
        for entry in entries:
            entry.setdefault("checked", True)
            self._files.append(entry)
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._files.clear()
        self.endResetModel()

    def get_checked(self) -> list[dict]:
        return [f for f in self._files if f["checked"]]

    def get_all(self) -> list[dict]:
        return list(self._files)

    def remove_rows(self, indices: list[int]):
        for i in sorted(indices, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self._files[i]
            self.endRemoveRows()

    def base_directory(self) -> str:
        if not self._files:
            return ""
        paths = [f["path"] for f in self._files]
        return os.path.commonpath(paths) if paths else ""

    def select_all(self):
        for f in self._files:
            f["checked"] = True
        self.layoutChanged.emit()

    def select_none(self):
        for f in self._files:
            f["checked"] = False
        self.layoutChanged.emit()

    def invert_selection(self):
        for f in self._files:
            f["checked"] = not f["checked"]
        self.layoutChanged.emit()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


class FileTableView(QTableView):
    files_dropped = Signal(list)

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

    def model(self) -> FileTableModel:
        return self._model

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
                    from datetime import datetime
                    entries.append({
                        "path": p,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "checked": True,
                    })
                except OSError:
                    pass
            self._model.add_files(entries)

    def _open_in_explorer(self):
        for idx in self.selectedIndexes():
            if idx.column() == self._model.COL_PATH:
                path = self._model._files[idx.row()]["path"]
                os.system(f'explorer /select,"{path}"')
                break

