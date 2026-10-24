import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QScrollArea,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog,
)

from shared.project import ProjectData
from shared.file_rules import FileRules
from shared.constants import SPACING_MD, SPACING_LG, SPACING_SM
from builder.ui.widgets.filter_panel import FilterPanel
from builder.ui.widgets.file_table import FileTableView, dedupe_key, path_key
from builder.ui.workers.scan_worker import ScanWorker


class Step1Files(QWidget):
    def __init__(self, project: ProjectData, parent=None):
        super().__init__(parent)
        self._project = project
        self._worker: ScanWorker | None = None
        self._all_files: list[dict] = []
        self._filtered_files: list[dict] = []
        self._known_paths: set[str] = set()
        self._base_dir = project.base_directory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, 0)
        layout.setSpacing(SPACING_MD)

        dir_bar = QFrame()
        dir_bar.setObjectName("dirBar")
        dir_bar.setProperty("cssClass", "panel")
        dir_layout = QVBoxLayout(dir_bar)
        dir_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        dir_layout.setSpacing(SPACING_SM)

        dir_label = QLabel("📂 选择源文件夹")
        dir_label.setProperty("cssClass", "h3")
        dir_label.setToolTip("选择需要生成校验文件的根目录，所有子文件将被扫描")
        dir_layout.addWidget(dir_label)

        dir_hint = QLabel("选择要验证完整性的目标文件夹，系统将递归扫描所有文件")
        dir_hint.setProperty("cssClass", "hint")
        dir_layout.addWidget(dir_hint)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(SPACING_SM)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("选择或拖拽文件夹到此处...")
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setToolTip("当前选择的根目录。所有文件路径将以此目录为基准生成相对路径")
        dir_row.addWidget(self._dir_edit, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setAccessibleName("选择源文件夹")
        browse_btn.setToolTip("打开文件对话框选择要扫描的根文件夹")
        browse_btn.clicked.connect(self._browse_directory)
        dir_row.addWidget(browse_btn)

        rescan_btn = QPushButton("重新扫描")
        rescan_btn.setProperty("cssClass", "secondary")
        rescan_btn.setAccessibleName("重新扫描当前文件夹")
        rescan_btn.setToolTip("重新扫描当前目录，更新文件列表")
        rescan_btn.clicked.connect(self._rescan)
        dir_row.addWidget(rescan_btn)

        dir_layout.addLayout(dir_row)
        layout.addWidget(dir_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        filter_frame = QFrame()
        filter_frame.setObjectName("filterFrame")
        filter_frame.setProperty("cssClass", "panel")
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
        self._file_table.setAccessibleName("文件列表")
        self._file_table.files_dropped.connect(self._on_files_dropped)
        self._file_table.files_added.connect(self._on_files_added)
        self._file_table.setToolTip(
            "文件列表。勾选/取消勾选来包含/排除文件。\n"
            "拖拽文件或文件夹到此处可直接添加。\n"
            "右键查看更多操作。"
        )
        right_layout.addWidget(self._file_table, 1)

        stats_bar = QFrame()
        stats_bar.setProperty("cssClass", "panel")
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        stats_layout.setSpacing(SPACING_MD)

        self._total_label = QLabel("总计: 0")
        self._total_label.setToolTip("扫描到的文件总数（不含过滤）")
        stats_layout.addWidget(self._total_label)

        self._filtered_label = QLabel("已过滤: 0")
        self._filtered_label.setProperty("cssClass", "accent")
        self._filtered_label.setToolTip("被过滤规则排除的文件数量")
        stats_layout.addWidget(self._filtered_label)

        self._selected_label = QLabel("已选: 0")
        self._selected_label.setToolTip("当前勾选/将参与校验的文件数量")
        stats_layout.addWidget(self._selected_label)

        stats_layout.addStretch()

        select_all = QPushButton("全选")
        select_all.setProperty("cssClass", "secondary")
        select_all.setMinimumHeight(32)
        select_all.setAccessibleName("勾选所有文件")
        select_all.setToolTip("勾选所有文件")
        select_all.clicked.connect(lambda: self._file_table.model().select_all())
        stats_layout.addWidget(select_all)

        invert = QPushButton("反选")
        invert.setProperty("cssClass", "secondary")
        invert.setMinimumHeight(32)
        invert.setAccessibleName("反转文件勾选状态")
        invert.setToolTip("反转当前勾选状态")
        invert.clicked.connect(lambda: self._file_table.model().invert_selection())
        stats_layout.addWidget(invert)

        add_btn = QPushButton("添加")
        add_btn.setProperty("cssClass", "secondary")
        add_btn.setMinimumHeight(32)
        add_btn.setAccessibleName("添加外部文件")
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
        self._next_btn.setAccessibleName("完成文件选择并进入哈希步骤")
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
        p.file_paths = [f["path"] for f in self._all_files]

        fd = self._filter_panel.get_filter_data()
        p.filter_enabled = fd["enabled"]
        p.filter_blacklist = fd["blacklist"]
        p.filter_extensions = fd["extensions"]
        p.filter_folders = fd["folders"]
        p.filter_min_size_kb = fd["min_size_kb"]
        p.filter_max_size_kb = fd["max_size_kb"]

        checked_keys = {
            dedupe_key(f)
            for f in self._file_table.model().get_checked()
        }
        p.checksum_entries = [
            {"path": self._make_relative(f["path"]), "hash": "", "status": "pending"}
            for f in self._all_files
            if dedupe_key(f) in checked_keys
        ]
        p.exclude_paths = [
            self._make_relative(f["path"])
            for f in self._all_files
            if dedupe_key(f) not in checked_keys
        ]

    def refresh_from_project(self):
        p = self._project
        self._base_dir = p.base_directory
        if p.base_directory:
            self._dir_edit.setText(p.base_directory)
        self._filter_panel.apply_from_project(p)

        self._known_paths.clear()
        entries = []
        excluded = {
            path_key(self._resolve_path(path))
            for path in p.exclude_paths
            if str(path).strip()
        }
        for path in p.file_paths:
            full_path = self._resolve_path(path)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            key = path_key(full_path)
            if key in self._known_paths:
                continue
            self._known_paths.add(key)
            entries.append({
                "_identity_key": key,
                "path": full_path,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "checked": key not in excluded,
            })
        self._all_files = entries
        self._apply_filters()

    def set_project(self, project: ProjectData):
        """Rebind to a freshly created or loaded project."""
        self._project = project
        self._known_paths.clear()
        self._all_files = []
        self._filtered_files = []
        self._file_table.model().clear()
        self.refresh_from_project()
        self._update_stats()

    def scan_directory(self, directory: str):
        self._base_dir = directory
        self._project.base_directory = directory
        self._dir_edit.setText(directory)

        # The scan always collects every file; filters are applied afterwards by
        # _apply_filters() so nothing can silently drop out of the manifest.
        self._worker = ScanWorker([directory])
        self._worker.files_found.connect(self._on_files_found)
        self._worker.scan_complete.connect(self._on_scan_complete)
        self._worker.error_occurred.connect(self._on_scan_error)

        self._all_files.clear()
        self._filtered_files.clear()
        self._known_paths.clear()
        self._file_table.model().clear()
        self._file_table.set_scanning(True)
        self._update_stats()
        self._worker.start()

    def _on_files_found(self, files: list[tuple[str, int, float]]):
        entries = []
        for path, size, mtime in files:
            key = path_key(path)
            if key in self._known_paths:
                continue
            self._known_paths.add(key)
            entries.append({
                "_identity_key": key,
                "path": path,
                "size": size,
                "mtime": mtime,
                "checked": True,
            })
        if not entries:
            return
        self._all_files.extend(entries)
        self._file_table.model().add_files(entries)
        self._update_stats()

    def _on_scan_complete(self, total: int, skipped: int = 0):
        self._worker = None
        self._file_table.set_scanning(False)
        self._apply_filters()
        self._update_stats()
        if skipped:
            from builder.ui.widgets.toast import show_toast
            show_toast(
                self,
                f"扫描完成，但有 {skipped} 个项目无法读取，已跳过",
                level="warning",
            )

    def _on_scan_error(self, msg: str):
        from builder.ui.widgets.toast import show_toast
        self._file_table.set_scanning(False)
        show_toast(self, f"扫描警告: {msg}", duration_ms=5000, level="warning")

    def _on_filters_changed(self):
        self._filter_timer.start()

    def _apply_filters(self):
        fd = self._filter_panel.get_filter_data()
        if not fd["enabled"]:
            self._file_table.model().set_files(self._all_files)
            self._filtered_files = self._all_files
        else:
            # The same FileRules object travels with the packed verifier, so
            # the preview and the shipped checks must agree on ignored files.
            rules = FileRules.from_filter_data(fd)
            filtered = [
                entry for entry in self._all_files
                if not rules.excludes(entry["path"], entry["size"])
            ]
            self._filtered_files = filtered
            self._file_table.model().set_files(filtered)
        self._update_stats()

    def _update_stats(self):
        total = len(self._all_files)
        filtered = total - len(self._filtered_files)
        selected = self._file_table.model().checked_count()
        self._total_label.setText(f"总计: {total:,}")
        self._filtered_label.setText(f"已过滤: {filtered:,}")
        self._selected_label.setText(f"已选: {selected:,}")

    def _on_files_added(self, entries: list[dict]):
        fresh = []
        for entry in entries:
            key = dedupe_key(entry)
            if key in self._known_paths:
                continue
            self._known_paths.add(key)
            entry["_identity_key"] = key
            fresh.append(entry)
        if not fresh:
            return
        self._all_files.extend(fresh)
        self._apply_filters()

    def _on_files_dropped(self, paths: list[str]):
        entries = []
        for p in paths:
            key = path_key(p)
            if key in self._known_paths:
                continue
            try:
                stat = os.stat(p)
            except OSError:
                continue
            self._known_paths.add(key)
            entries.append({
                "_identity_key": key,
                "path": p,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "checked": True,
            })
        if not entries:
            return
        self._all_files.extend(entries)
        # Run dropped files through the same filter pipeline as scanned files.
        self._apply_filters()
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

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path) or not self._base_dir:
            return path
        return os.path.join(self._base_dir, path)

