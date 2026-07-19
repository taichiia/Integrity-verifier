from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame,
)
from shared.constants import (
    SPACING_MD, SPACING_LG, FONT_H3_SIZE, FONT_BODY_SIZE,
    LIFTED_CREAM, DUST_TAUPE, RADIUS_HERO,
)


class StatsPanel(QFrame):
    rescan_clicked = Signal()
    directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatsPanel")
        self.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_MD)

        title = QLabel("Statistics")
        title.setProperty("cssClass", "h3")
        layout.addWidget(title)

        self._total_label = QLabel("Total: 0")
        self._total_label.setStyleSheet(f"font-size: {FONT_BODY_SIZE}px;")
        layout.addWidget(self._total_label)

        self._filtered_label = QLabel("Filtered: 0")
        self._filtered_label.setStyleSheet(f"font-size: {FONT_BODY_SIZE}px; color: #CF4500;")
        layout.addWidget(self._filtered_label)

        self._selected_label = QLabel("Selected: 0")
        self._selected_label.setStyleSheet(f"font-size: {FONT_BODY_SIZE}px;")
        layout.addWidget(self._selected_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep)

        select_all = QPushButton("Select All")
        select_all.setProperty("cssClass", "secondary")
        select_all.setFixedHeight(30)
        layout.addWidget(select_all)

        invert = QPushButton("Invert Selection")
        invert.setProperty("cssClass", "secondary")
        invert.setFixedHeight(30)
        layout.addWidget(invert)

        add_ext = QPushButton("Add Files...")
        add_ext.setProperty("cssClass", "secondary")
        add_ext.setFixedHeight(30)
        layout.addWidget(add_ext)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {DUST_TAUPE};")
        layout.addWidget(sep2)

        dir_label = QLabel("Base Directory:")
        dir_label.setProperty("cssClass", "eyebrow")
        layout.addWidget(dir_label)

        self._dir_label = QLabel("(not set)")
        self._dir_label.setWordWrap(True)
        self._dir_label.setStyleSheet(f"font-size: 11px; color: #696969;")
        layout.addWidget(self._dir_label)

        change_dir = QPushButton("Change...")
        change_dir.setProperty("cssClass", "secondary")
        change_dir.setFixedHeight(30)
        change_dir.clicked.connect(self._change_directory)
        layout.addWidget(change_dir)

        rescan = QPushButton("Rescan")
        rescan.setFixedHeight(30)
        rescan.clicked.connect(self.rescan_clicked.emit)
        layout.addWidget(rescan)

        layout.addStretch()

        select_all.clicked.connect(lambda: self._request_action("select_all"))
        invert.clicked.connect(lambda: self._request_action("invert"))
        add_ext.clicked.connect(self._add_external_files)

    action_requested = Signal(str)

    def _request_action(self, action: str):
        self.action_requested.emit(action)

    def _add_external_files(self):
        self.action_requested.emit("add_external")

    def _change_directory(self):
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "Select Base Directory")
        if path:
            self._dir_label.setText(path)
            self.directory_changed.emit(path)

    def update_stats(self, total: int, filtered: int, selected: int,
                     base_dir: str = ""):
        self._total_label.setText(f"Total: {total:,}")
        self._filtered_label.setText(f"Filtered: {filtered:,}")
        self._selected_label.setText(f"Selected: {selected:,}")
        if base_dir:
            self._dir_label.setText(base_dir)

    def set_base_directory(self, path: str):
        self._dir_label.setText(path)

