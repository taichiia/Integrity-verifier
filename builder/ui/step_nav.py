from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
)


class StepNav(QFrame):
    step_changed = Signal(int)

    STEPS = ["选择文件", "生成校验文件", "打包验证器"]
    STEPS_SHORT = ["选择文件", "生成校验", "打包部署"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("cssClass", "bottom-nav")
        self.setFixedHeight(52)
        self.setMinimumWidth(280)
        self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        self._current = 0
        self._completed: set[int] = set()
        self._prerequisite: dict[int, set[int]] = {1: {0}, 2: {1}}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: list[QPushButton] = []

        for index, label in enumerate(self.STEPS):
            button = QPushButton(label, self)
            button.setProperty("cssClass", "nav-item")
            button.setCheckable(False)
            button.setMinimumHeight(46)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setAccessibleName(f"步骤 {index + 1}：{label}")
            button.setToolTip(f"切换到{label}。使用 Ctrl+{index + 1} 可直接跳转。")
            button.clicked.connect(lambda checked=False, idx=index: self._on_clicked(idx))
            layout.addWidget(button, 1)
            self._buttons.append(button)

        self._refresh_states()

    def set_current(self, index: int):
        if 0 <= index < len(self._buttons):
            self._current = index
            self._refresh_states()

    def set_completed(self, index: int, completed: bool = True):
        if completed:
            self._completed.add(index)
        else:
            self._completed.discard(index)
        self._refresh_states()

    def current(self) -> int:
        return self._current

    def _on_clicked(self, index: int):
        required = self._prerequisite.get(index, set())
        if index != self._current and not required.issubset(self._completed):
            return
        self.step_changed.emit(index)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._move_focus(-1)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._move_focus(1)
        elif key == Qt.Key.Key_Home:
            self._focus_enabled_index(0)
        elif key == Qt.Key.Key_End:
            self._focus_enabled_index(-1)
        else:
            super().keyPressEvent(event)

    def _move_focus(self, direction: int):
        enabled = self._enabled_indexes()
        if not enabled:
            return

        focused = QApplication.focusWidget()
        try:
            position = enabled.index(self._buttons.index(focused))
        except (ValueError, RuntimeError):
            position = enabled.index(self._current)

        target = enabled[(position + direction) % len(enabled)]
        self._buttons[target].setFocus(Qt.FocusReason.TabFocusReason)

    def _focus_enabled_index(self, position: int):
        enabled = self._enabled_indexes()
        if not enabled:
            return
        target = enabled[position]
        self._buttons[target].setFocus(Qt.FocusReason.TabFocusReason)

    def _enabled_indexes(self) -> list[int]:
        return [
            index for index, button in enumerate(self._buttons)
            if button.isEnabled()
        ]

    def _refresh_states(self):
        for index, button in enumerate(self._buttons):
            selected = index == self._current
            completed = index in self._completed
            available = (
                selected
                or self._prerequisite.get(index, set()).issubset(self._completed)
            )
            button.setProperty("navState", "selected" if selected else "default")
            button.setEnabled(available)

            if selected:
                label = self.STEPS[index]
                tooltip = f"当前步骤：{label}"
            elif not available:
                label = self.STEPS_SHORT[index]
                tooltip = "前置步骤尚未完成。"
            elif completed:
                label = f"已完成 · {self.STEPS_SHORT[index]}"
                tooltip = f"{self.STEPS_SHORT[index]}已完成，点击返回。"
            else:
                label = self.STEPS[index]
                tooltip = f"切换到{label}。使用 Ctrl+{index + 1} 可直接跳转。"

            button.setText(label)
            button.setToolTip(tooltip)
            suffix = "" if available else "，未解锁"
            button.setAccessibleName(f"步骤 {index + 1}：{label}{suffix}")

        self.style().unpolish(self)
        self.style().polish(self)
        for button in self._buttons:
            button.style().unpolish(button)
            button.style().polish(button)

        focused = QApplication.focusWidget()
        if focused in self._buttons and not focused.isEnabled():
            self._buttons[self._current].setFocus(
                Qt.FocusReason.TabFocusReason
            )
