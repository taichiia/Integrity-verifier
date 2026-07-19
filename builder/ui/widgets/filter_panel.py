from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QRadioButton,
    QPushButton, QLabel, QLineEdit, QSpinBox, QListWidget, QListWidgetItem,
    QButtonGroup, QFrame,
)
from shared.constants import (
    INK_BLACK, SLATE_GRAY, SIGNAL_ORANGE, DUST_TAUPE, LIFTED_CREAM,
    SPACING_SM, SPACING_MD, RADIUS_HERO,
)


class FilterPanel(QWidget):
    filters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel("• 过滤规则")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {INK_BLACK}; "
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        title.setToolTip("设置文件过滤规则，排除不需要校验的文件")
        layout.addWidget(title)

        self._enable_cb = QCheckBox("启用过滤")
        self._enable_cb.setChecked(True)
        self._enable_cb.setToolTip("开启/关闭所有过滤规则。关闭时所有文件都将被包含")
        self._enable_cb.toggled.connect(self.filters_changed.emit)
        layout.addWidget(self._enable_cb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep)

        mode_label = QLabel("过滤模式")
        mode_label.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {SLATE_GRAY};")
        mode_label.setToolTip("黑名单：排除匹配的文件 | 白名单：仅保留匹配的文件")
        layout.addWidget(mode_label)

        mode_group = QButtonGroup(self)
        mode_layout = QHBoxLayout()
        self._blacklist_rb = QRadioButton("黑名单")
        self._blacklist_rb.setChecked(True)
        self._blacklist_rb.setToolTip("排除与规则匹配的文件（常用：排除日志、临时文件）")
        self._whitelist_rb = QRadioButton("白名单")
        self._whitelist_rb.setToolTip("仅保留与规则匹配的文件")
        mode_group.addButton(self._blacklist_rb)
        mode_group.addButton(self._whitelist_rb)
        mode_layout.addWidget(self._blacklist_rb)
        mode_layout.addWidget(self._whitelist_rb)
        mode_group.buttonClicked.connect(self.filters_changed.emit)
        layout.addLayout(mode_layout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep2)

        ext_label = QLabel("扩展名")
        ext_label.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {SLATE_GRAY};")
        ext_label.setToolTip("按文件扩展名过滤。例：添加 .log 可排除所有日志文件")
        layout.addWidget(ext_label)

        self._ext_list = QListWidget()
        self._ext_list.setMaximumHeight(120)
        self._ext_list.setToolTip("被过滤的扩展名列表。双击可编辑，右键可删除")
        for ext in [".log", ".tmp", ".bak"]:
            item = QListWidgetItem(ext)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._ext_list.addItem(item)
        layout.addWidget(self._ext_list)

        ext_add_layout = QHBoxLayout()
        self._ext_input = QLineEdit()
        self._ext_input.setPlaceholderText("扩展名（如 .exe）")
        self._ext_input.setToolTip("输入要添加的扩展名，包含点号")
        ext_add_layout.addWidget(self._ext_input)
        ext_add_btn = QPushButton("+ 添加")
        ext_add_btn.setFixedWidth(70)
        ext_add_btn.clicked.connect(self._add_extension)
        ext_add_layout.addWidget(ext_add_btn)
        layout.addLayout(ext_add_layout)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep3)

        folder_label = QLabel("文件夹名")
        folder_label.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {SLATE_GRAY};")
        folder_label.setToolTip("按父文件夹名过滤。例：添加 .git 可排除所有git仓库中的文件")
        layout.addWidget(folder_label)

        self._folder_list = QListWidget()
        self._folder_list.setMaximumHeight(120)
        self._folder_list.setToolTip("被过滤的文件夹名列表。匹配这些名称的文件夹中的文件将被过滤")
        for folder in [".git", "node_modules", "__pycache__", ".venv"]:
            self._folder_list.addItem(QListWidgetItem(folder))
        layout.addWidget(self._folder_list)

        folder_add_layout = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("文件夹名")
        self._folder_input.setToolTip("输入要过滤的文件夹名（不区分大小写）")
        folder_add_layout.addWidget(self._folder_input)
        folder_add_btn = QPushButton("+ 添加")
        folder_add_btn.setFixedWidth(70)
        folder_add_btn.clicked.connect(self._add_folder)
        folder_add_layout.addWidget(folder_add_btn)
        layout.addLayout(folder_add_layout)

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep4)

        size_label = QLabel("文件大小")
        size_label.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {SLATE_GRAY};")
        size_label.setToolTip("按文件大小过滤。设0表示不限制")
        layout.addWidget(size_label)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("最小:"))
        self._min_spin = QSpinBox()
        self._min_spin.setRange(0, 9999999)
        self._min_spin.setSuffix(" KB")
        self._min_spin.setToolTip("排除小于此大小的文件。0 = 无限制")
        self._min_spin.valueChanged.connect(self.filters_changed.emit)
        size_row.addWidget(self._min_spin)
        layout.addLayout(size_row)

        size_row2 = QHBoxLayout()
        size_row2.addWidget(QLabel("最大:"))
        self._max_spin = QSpinBox()
        self._max_spin.setRange(0, 9999999)
        self._max_spin.setSpecialValueText("不限制")
        self._max_spin.setSuffix(" KB")
        self._max_spin.setToolTip("排除大于此大小的文件。0 = 无限制")
        self._max_spin.valueChanged.connect(self.filters_changed.emit)
        size_row2.addWidget(self._max_spin)
        layout.addLayout(size_row2)

        layout.addStretch()

    def _add_extension(self):
        text = self._ext_input.text().strip()
        if text:
            if not text.startswith("."):
                text = "." + text
            self._ext_list.addItem(QListWidgetItem(text))
            self._ext_input.clear()
            self.filters_changed.emit()

    def _add_folder(self):
        text = self._folder_input.text().strip()
        if text:
            self._folder_list.addItem(QListWidgetItem(text))
            self._folder_input.clear()
            self.filters_changed.emit()

    def get_filter_data(self) -> dict:
        exts = []
        for i in range(self._ext_list.count()):
            exts.append(self._ext_list.item(i).text().strip().lstrip("."))
        folders = []
        for i in range(self._folder_list.count()):
            folders.append(self._folder_list.item(i).text().strip())

        return {
            "enabled": self._enable_cb.isChecked(),
            "blacklist": self._blacklist_rb.isChecked(),
            "extensions": exts,
            "folders": folders,
            "min_size_kb": self._min_spin.value(),
            "max_size_kb": self._max_spin.value(),
        }

    def apply_from_project(self, proj_data):
        self._enable_cb.setChecked(proj_data.filter_enabled)
        self._blacklist_rb.setChecked(proj_data.filter_blacklist)
        self._whitelist_rb.setChecked(not proj_data.filter_blacklist)

        self._ext_list.clear()
        for ext in proj_data.filter_extensions:
            self._ext_list.addItem(QListWidgetItem(ext))

        self._folder_list.clear()
        for f in proj_data.filter_folders:
            self._folder_list.addItem(QListWidgetItem(f))

        self._min_spin.setValue(proj_data.filter_min_size_kb)
        self._max_spin.setValue(proj_data.filter_max_size_kb)

