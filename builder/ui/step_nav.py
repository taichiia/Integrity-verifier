from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QFont, QColor, QPainterPath
from PySide6.QtWidgets import QWidget, QSizePolicy

from shared.constants import FONT_FAMILY
from shared.theme import get_palette

TAB_WIDTH = 180
TAB_HEIGHT = 44
TAB_PADDING = 12


class StepNav(QWidget):
    step_changed = Signal(int)

    STEPS = ["① 选择文件", "② 生成校验文件", "③ 打包验证器"]
    STEPS_SHORT = ["选择文件", "生成校验", "打包部署"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TAB_HEIGHT + TAB_PADDING * 2)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._current = 0
        self._completed: set[int] = set()
        self._prerequisite: dict[int, set[int]] = {1: {0}, 2: {1}}
        self.setMouseTracking(True)

    def set_current(self, index: int):
        self._current = index
        self.update()

    def set_completed(self, index: int, completed: bool = True):
        if completed:
            self._completed.add(index)
        else:
            self._completed.discard(index)
        self.update()

    def current(self) -> int:
        return self._current

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = get_palette()
        primary = pal["primary"]
        accent_hover = pal["accent_hover"]
        text_color_token = pal["text"]
        surface = pal["surface"]
        secondary = pal["secondary"]
        border = pal["border"]

        total_w = len(self.STEPS) * TAB_WIDTH + (len(self.STEPS) - 1) * 8
        start_x = (self.width() - total_w) // 2
        start_y = TAB_PADDING

        for i in range(3):
            x = start_x + i * (TAB_WIDTH + 8)
            active = i == self._current
            completed = i in self._completed

            rect = QRect(x, start_y, TAB_WIDTH, TAB_HEIGHT)
            path = QPainterPath()
            path.addRoundedRect(rect, TAB_HEIGHT // 2, TAB_HEIGHT // 2)

            if active:
                p.setBrush(QBrush(QColor(primary)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(path)
                text_color = QColor("#FFFFFF")
                weight = QFont.Weight.Bold
            elif completed:
                p.setBrush(QBrush(QColor(accent_hover)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(path)
                text_color = QColor("#FFFFFF")
                weight = QFont.Weight.Medium
            else:
                p.setBrush(QBrush(QColor(surface)))
                p.setPen(QPen(QColor(border), 1.5))
                p.drawPath(path)
                text_color = QColor(secondary)
                weight = QFont.Weight.Normal

            label = self.STEPS[i]
            if completed:
                label = f"✓ {self.STEPS_SHORT[i]}"

            p.setPen(QPen(text_color))
            font = QFont(FONT_FAMILY, 13, weight)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        total_w = len(self.STEPS) * TAB_WIDTH + (len(self.STEPS) - 1) * 8
        start_x = (self.width() - total_w) // 2
        x = event.position().x()
        y = event.position().y()

        if TAB_PADDING <= y <= TAB_PADDING + TAB_HEIGHT:
            for i in range(3):
                tab_x = start_x + i * (TAB_WIDTH + 8)
                if tab_x <= x <= tab_x + TAB_WIDTH:
                    required = self._prerequisite.get(i, set())
                    if not required.issubset(self._completed) and i != self._current:
                        return
                    self.step_changed.emit(i)
                    return

