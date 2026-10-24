from PySide6.QtWidgets import QPushButton

from builder.ui.main_window import BuilderMainWindow
from builder.ui.widgets.file_table import FileTableModel


def test_main_window_reduces_navigation_gap(qapp):
    window = BuilderMainWindow()
    window.show()

    central_layout = window.centralWidget().layout()
    page_layout = window._stack.parentWidget().layout()

    assert central_layout.contentsMargins().bottom() == 8
    assert page_layout.contentsMargins().bottom() == 16
    window.deleteLater()


def test_step1_add_button_stays_compact_and_accessible(qapp):
    window = BuilderMainWindow()
    buttons = [
        button for button in window._step1.findChildren(QPushButton)
        if button.accessibleName() == "添加外部文件"
    ]

    assert len(buttons) == 1
    assert buttons[0].text() == "添加"
    assert buttons[0].toolTip() == "手动添加不在当前目录中的外部文件"
    window.deleteLater()


def test_file_model_skips_reset_for_same_entries(qapp):
    entries = [
        {"path": f"file-{index}.txt", "size": index, "mtime": 0, "checked": True}
        for index in range(3)
    ]
    model = FileTableModel()
    model.set_files(entries)
    resets = []
    model.modelReset.connect(lambda: resets.append(True))

    assert model.set_files(entries) == 0
    assert resets == []
    assert model.rowCount() == 3
