from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PySide6.QtWidgets import QLabel, QFrame, QGraphicsOpacityEffect
from shared.constants import (
    INK_BLACK, CANVAS_CREAM, SUCCESS_GREEN, ERROR_RED, WARNING_AMBER,
    RADIUS_CHIP, FONT_BODY_SIZE, SPACING_MD,
)


class Toast(QFrame):
    def __init__(self, message: str, duration_ms: int = 3000,
                 level: str = "info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        colors = {
            "info": INK_BLACK,
            "success": SUCCESS_GREEN,
            "warning": WARNING_AMBER,
            "error": ERROR_RED,
        }
        bg = colors.get(level, INK_BLACK)

        self.setStyleSheet(f"""
            Toast {{
                background-color: {bg};
                border-radius: {RADIUS_CHIP}px;
                padding: {SPACING_MD}px;
            }}
        """)

        label = QLabel(message, self)
        label.setStyleSheet(f"color: {CANVAS_CREAM}; font-size: {FONT_BODY_SIZE}px; "
                           f"font-weight: 500; background: transparent;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.adjustSize()
        self.resize(label.width() + SPACING_MD * 4, label.height() + SPACING_MD * 2)
        label.setGeometry(SPACING_MD * 2, SPACING_MD, label.width(), label.height())

        if parent:
            pp = parent.mapToGlobal(QPoint(0, 0))
            x = pp.x() + (parent.width() - self.width()) // 2
            y = pp.y() + parent.height() - self.height() - 40
            self.move(x, y)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0)
        self._anim.setEndValue(1)
        self._anim.start()

        self.show()
        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1)
        self._anim.setEndValue(0)
        self._anim.finished.connect(self.close)
        self._anim.start()


def show_toast(parent, message: str, duration_ms: int = 3000,
               level: str = "info"):
    return Toast(message, duration_ms, level, parent)

