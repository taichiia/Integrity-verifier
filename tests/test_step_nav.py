from PySide6.QtWidgets import QApplication

from builder.ui.step_nav import StepNav


def test_locked_steps_are_disabled_and_described(qapp):
    nav = StepNav()

    assert nav._buttons[0].isEnabled()
    assert not nav._buttons[1].isEnabled()
    assert not nav._buttons[2].isEnabled()
    assert "未解锁" in nav._buttons[1].accessibleName()
    assert nav._buttons[1].toolTip() == "前置步骤尚未完成。"

    nav.set_completed(0)
    nav.set_current(1)

    assert nav._buttons[0].isEnabled()
    assert nav._buttons[1].isEnabled()
    assert not nav._buttons[2].isEnabled()

    nav.set_completed(1)

    assert nav._buttons[2].isEnabled()


def test_keyboard_navigation_skips_locked_steps(qapp):
    nav = StepNav()
    nav.show()
    qapp.processEvents()
    nav._buttons[0].setFocus()

    nav._move_focus(1)

    assert QApplication.focusWidget() is nav._buttons[0]

    nav.set_completed(0)
    nav._buttons[0].setFocus()
    nav._move_focus(1)

    assert QApplication.focusWidget() is nav._buttons[1]
