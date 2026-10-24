from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from shared.constants import (
    SIGNAL_ORANGE, FONT_H3_SIZE, SPACING_MD, SPACING_LG,
)


class CardWidget(QFrame):
    def __init__(self, title: str, parent=None, collapsed: bool = False):
        super().__init__(parent)
        self._collapsed = collapsed
        self._title = title

        self.setObjectName("CardWidget")
        self.setProperty("cssClass", "panel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        self._layout.setSpacing(SPACING_MD)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        dot = QLabel("•")
        dot.setProperty("cssClass", "accent")
        dot.setFixedWidth(16)
        header.addWidget(dot)

        self._title_label = QLabel(title)
        self._title_label.setProperty("cssClass", "h3")
        header.addWidget(self._title_label, 1)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setProperty("cssClass", "icon-circle")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setAccessibleName(f"expand-or-collapse-{title}")
        self._toggle_btn.setToolTip("展开或收起此卡片")
        self._toggle_btn.setText("▴" if collapsed else "▾")
        self._toggle_btn.clicked.connect(self.toggle)
        header.addWidget(self._toggle_btn)

        self._layout.addLayout(header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SPACING_MD)
        self._layout.addWidget(self._content)

        if collapsed:
            self._content.hide()

    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def add_layout(self, layout: QHBoxLayout | QVBoxLayout):
        self._content_layout.addLayout(layout)

    def toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("▴" if self._collapsed else "▾")

    def content_widget(self) -> QWidget:
        return self._content

