from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from shared.constants import (
    LIFTED_CREAM, INK_BLACK, DUST_TAUPE, SIGNAL_ORANGE,
    FONT_H3_SIZE, SPACING_MD, SPACING_LG, RADIUS_HERO,
)


class CardWidget(QFrame):
    def __init__(self, title: str, parent=None, collapsed: bool = False):
        super().__init__(parent)
        self._collapsed = collapsed
        self._title = title

        self.setObjectName("CardWidget")
        self.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        self._layout.setSpacing(SPACING_MD)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        dot = QLabel("•")
        dot.setStyleSheet(f"color: {SIGNAL_ORANGE}; font-size: 16px; font-weight: 700;")
        dot.setFixedWidth(16)
        header.addWidget(dot)

        self._title_label = QLabel(title)
        self._title_label.setProperty("cssClass", "h3")
        self._title_label.setStyleSheet(f"font-size: {FONT_H3_SIZE}px; font-weight: 500;")
        header.addWidget(self._title_label, 1)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setProperty("cssClass", "icon-circle")
        self._toggle_btn.setFixedSize(28, 28)
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

