import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QScrollArea,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog,
)

from shared.project import ProjectData
from shared.constants import (
    SPACING_MD, SPACING_LG, SPACING_SM, FONT_H3_SIZE, FONT_BODY_SIZE, FONT_EYEBROW_SIZE,
    LIFTED_CREAM, DUST_TAUPE, RADIUS_HERO, SLATE_GRAY, INK_BLACK,
    SUCCESS_GREEN, WARNING_AMBER, SIGNAL_ORANGE,
)
from builder.ui.widgets.filter_panel import FilterPanel
from builder.ui.widgets.file_table import FileTableView
from builder.ui.workers.scan_worker import ScanWorker


class Step1Files(QWidget):
    def __init__(self, project: ProjectData, parent=None):
        super().__init__(parent)
        self._project = project
        self._worker: ScanWorker | None = None
        self._all_files: list[dict] = []
        self._filtered_files: list[dict] = []
        self._base_dir = project.base_directory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, 0)
        layout.setSpacing(SPACING_MD)

        dir_bar = QFrame()
        dir_bar.setObjectName("dirBar")
        dir_bar.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)
        dir_layout = QVBoxLayout(dir_bar)
        dir_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        dir_layout.setSpacing(SPACING_SM)

        dir_label = QLabel("📂 选择源文件夹")
        dir_label.setProperty("cssClass", "h3")
        dir_label.setToolTip("选择需要生成校验文件的根目录，所有子文件将被扫描")
        dir_layout.addWidget(dir_label)

        dir_hint = QLabel("选择要验证完整性的目标文件夹，系统将递归扫描所有文件")
        dir_hint.setProperty("cssClass", "muted")
        dir_hint.setStyleSheet(f"font-size: {FONT_EYEBROW_SIZE}px; color: {SLATE_GRAY};")
        dir_layout.addWidget(dir_hint)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(SPACING_SM)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("选择或拖拽文件夹到此处...")
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setToolTip("当前选择的根目录。所有文件路径将以此目录为基准生成相对路径")
        dir_row.addWidget(self._dir_edit, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setToolTip("打开文件对话框选择要扫描的根文件夹")
        browse_btn.clicked.connect(self._browse_directory)
        dir_row.addWidget(browse_btn)

        rescan_btn = QPushButton("重新扫描")
        rescan_btn.setProperty("cssClass", "secondary")
        rescan_btn.setToolTip("重新扫描当前目录，更新文件列表")
        rescan_btn.clicked.connect(self._rescan)
        dir_row.addWidget(rescan_btn)

        dir_layout.addLayout(dir_row)
        layout.addWidget(dir_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        filter_frame = QFrame()
        filter_frame.setObjectName("filterFrame")
        filter_frame.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
            }}
        """)
        filter_inner = QVBoxLayout(filter_frame)
        filter_inner.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._filter_panel = FilterPanel()
        self._filter_panel.filters_changed.connect(self._on_filters_changed)
        scroll.setWidget(self._filter_panel)
        filter_inner.addWidget(scroll)
        splitter.addWidget(filter_frame)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING_SM)

        self._file_table = FileTableView()
        self._file_table.files_dropped.connect(self._on_files_dropped)
        self._file_table.setToolTip(
            "文件列表。勾选/取消勾选来包含/排除文件。\n"
            "拖拽文件或文件夹到此处可直接添加。\n"
            "右键查看更多操作。"
        )
        right_layout.addWidget(self._file_table, 1)

        stats_bar = QFrame()
        stats_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(12, 6, 12, 6)
        stats_layout.setSpacing(SPACING_LG)

        self._total_label = QLabel("总计: 0")
        self._total_label.setToolTip("扫描到的文件总数（不含过滤）")
        stats_layout.addWidget(self._total_label)

        self._filtered_label = QLabel("已过滤: 0")
        self._filtered_label.setStyleSheet(f"color: {SIGNAL_ORANGE}; font-weight: 500;")
        self._filtered_label.setToolTip("被过滤规则排除的文件数量")
        stats_layout.addWidget(self._filtered_label)

        self._selected_label = QLabel("已选: 0")
        self._selected_label.setStyleSheet(f"color: {INK_BLACK}; font-weight: 500;")
        self._selected_label.setToolTip("当前勾选/将参与校验的文件数量")
        stats_layout.addWidget(self._selected_label)

        stats_layout.addStretch()

        select_all = QPushButton("全选")
        select_all.setProperty("cssClass", "secondary")
        select_all.setFixedHeight(26)
        select_all.setToolTip("勾选所有文件")
        select_all.clicked.connect(lambda: self._file_table.model().select_all())
        stats_layout.addWidget(select_all)

        invert = QPushButton("反选")
        invert.setProperty("cssClass", "secondary")
        invert.setFixedHeight(26)
        invert.setToolTip("反转当前勾选状态")
        invert.clicked.connect(lambda: self._file_table.model().invert_selection())
        stats_layout.addWidget(invert)

        add_btn = QPushButton("添加文件...")
        add_btn.setProperty("cssClass", "secondary")
        add_btn.setFixedHeight(26)
        add_btn.setToolTip("手动添加不在当前目录中的外部文件")
        add_btn.clicked.connect(lambda: self._file_table._add_external())
        stats_layout.addWidget(add_btn)

        right_layout.addWidget(stats_bar)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 700])

        layout.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._next_btn = QPushButton("✓ 完成，进入下一步 →")
        self._next_btn.setToolTip("保存当前选择并进入「生成校验文件」步骤。\n所有勾选的文件将作为待校验清单")
        self._next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self._next_btn)

        layout.addLayout(btn_row)

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(500)
        self._filter_timer.timeout.connect(self._apply_filters)

    def _go_next(self):
        self.sync_to_project()
        w = self.window()
        if hasattr(w, '_step_nav'):
            w._step_nav.set_completed(0, True)
            w._step_nav.step_changed.emit(1)

    def _browse_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择源文件夹")
        if path:
            self._dir_edit.setText(path)
            self.scan_directory(path)

    def sync_to_project(self):
        p = self._project
        p.base_directory = self._base_dir
        p.file_paths = [f["path"] for f in self._file_table.model().get_all()]

        fd = self._filter_panel.get_filter_data()
        p.filter_enabled = fd["enabled"]
        p.filter_blacklist = fd["blacklist"]
        p.filter_extensions = fd["extensions"]
        p.filter_folders = fd["folders"]
        p.filter_min_size_kb = fd["min_size_kb"]
        p.filter_max_size_kb = fd["max_size_kb"]

        checked = self._file_table.model().get_checked()
        p.checksum_entries = [
            {"path": self._make_relative(f["path"]), "hash": "", "status": "pending"}
            for f in checked
        ]

    def refresh_from_project(self):
        p = self._project
        self._base_dir = p.base_directory
        if p.base_directory:
            self._dir_edit.setText(p.base_directory)
        self._filter_panel.apply_from_project(p)

        if p.file_paths:
            entries = []
            for path in p.file_paths:
                try:
                    stat = os.stat(path)
                    entries.append({
                        "path": path,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "checked": True,
                    })
                except OSError:
                    pass
            self._all_files = entries
            self._apply_filters()

    def scan_directory(self, directory: str):
        self._base_dir = directory
        self._project.base_directory = directory
        self._dir_edit.setText(directory)

        fd = self._filter_panel.get_filter_data()
        self._worker = ScanWorker(
            [directory],
            filter_extensions=fd["extensions"],
            filter_folders=fd["folders"],
            filter_blacklist=fd["blacklist"],
            filter_min_size=fd["min_size_kb"] * 1024,
            filter_max_size=fd["max_size_kb"] * 1024,
        )
        self._worker.file_found.connect(self._on_file_found)
        self._worker.scan_complete.connect(self._on_scan_complete)
        self._worker.error_occurred.connect(self._on_scan_error)

        self._all_files.clear()
        self._file_table.model().clear()
        self._update_stats()
        self._worker.start()

    def _on_file_found(self, path: str, size: int, modified: str):
        entry = {"path": path, "size": size, "modified": modified, "checked": True}
        self._all_files.append(entry)
        self._file_table.model().add_files([entry])
        self._update_stats()

    def _on_scan_complete(self, total: int):
        self._worker = None
        self._apply_filters()
        self._update_stats()

    def _on_scan_error(self, msg: str):
        pass

    def _on_filters_changed(self):
        self._filter_timer.start()

    def _apply_filters(self):
        if not self._all_files:
            return
        fd = self._filter_panel.get_filter_data()
        if not fd["enabled"]:
            self._file_table.model().set_files(self._all_files)
            self._filtered_files = self._all_files
        else:
            exts = [e.lower() for e in fd["extensions"]]
            folders = [f.lower() for f in fd["folders"]]
            min_bytes = fd["min_size_kb"] * 1024
            max_bytes = fd["max_size_kb"] * 1024

            filtered = []
            for entry in self._all_files:
                path = entry["path"]
                ext = os.path.splitext(os.path.basename(path))[1].lower().lstrip(".")

                if min_bytes > 0 and entry["size"] < min_bytes:
                    continue
                if max_bytes > 0 and entry["size"] > max_bytes:
                    continue

                ext_match = ext in exts
                if exts:
                    if fd["blacklist"] and ext_match:
                        continue
                    if not fd["blacklist"] and not ext_match:
                        continue

                if folders:
                    has_folder_match = self._path_contains_folder(path, folders)
                    if fd["blacklist"] and has_folder_match:
                        continue
                    if not fd["blacklist"] and not has_folder_match:
                        continue

                filtered.append(entry)
            self._filtered_files = filtered
            self._file_table.model().set_files(filtered)
        self._update_stats()

    def _update_stats(self):
        total = len(self._all_files)
        filtered = total - len(self._filtered_files)
        selected = len(self._file_table.model().get_checked())
        self._total_label.setText(f"总计: {total:,}")
        self._filtered_label.setText(f"已过滤: {filtered:,}")
        self._selected_label.setText(f"已选: {selected:,}")

    def _on_files_dropped(self, paths: list[str]):
        entries = []
        for p in paths:
            try:
                stat = os.stat(p)
                entries.append({
                    "path": p,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "checked": True,
                })
            except OSError:
                pass
        self._all_files.extend(entries)
        self._filtered_files.extend(entries)
        self._file_table.model().add_files(entries)
        self._update_stats()

    def _rescan(self):
        if self._base_dir:
            self.scan_directory(self._base_dir)

    def _make_relative(self, abs_path: str) -> str:
        if self._base_dir:
            try:
                return os.path.relpath(abs_path, self._base_dir)
            except ValueError:
                return abs_path
        return abs_path

    @staticmethod
    def _path_contains_folder(path: str, folders: set) -> bool:
        parts = set(p.lower() for p in path.replace("\\", "/").split("/") if p)
        return bool(parts & set(folders))

