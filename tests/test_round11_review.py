from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from builder.ui.main_window import BuilderMainWindow
from builder.ui.widgets.file_table import FileTableModel
from shared.preferences import create_settings
from shared.theme import set_theme_mode
from shared.theme import generate_builder_stylesheet
from verifier.ui.main_window import VerifierResultModel


def test_verifier_model_clear_does_not_mutate_shared_results(qapp):
    shared = [
        {"path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc"},
    ]
    model = VerifierResultModel()
    model.set_results(shared)

    model.clear()

    assert model.rowCount() == 0
    assert len(shared) == 1


def test_file_model_clear_does_not_mutate_shared_files(qapp):
    shared = [{"path": "a.txt", "size": 1, "modified": "", "checked": True}]
    model = FileTableModel()
    model.set_files(shared)

    model.clear()

    assert model.rowCount() == 0
    assert len(shared) == 1


def test_builder_registers_all_step_shortcuts(qapp, tmp_path):
    settings = create_settings(tmp_path / "settings.ini")
    window = BuilderMainWindow(settings=settings)
    try:
        shortcuts = {
            action.shortcut().toString()
            for action in window.actions()
        }
        assert {"Ctrl+1", "Ctrl+2", "Ctrl+3"} <= shortcuts
    finally:
        window.close()
        set_theme_mode("light")


def test_builder_file_step_controls_have_accessible_names(qapp, tmp_path):
    settings = create_settings(tmp_path / "settings.ini")
    window = BuilderMainWindow(settings=settings)
    try:
        step = window._step1
        names = {
            child.accessibleName()
            for child in step.findChildren(QPushButton)
        }
        assert "选择源文件夹" in names
        assert "重新扫描当前文件夹" in names
        assert "勾选所有文件" in names
        assert "反转文件勾选状态" in names
        assert "添加外部文件" in names
        assert "完成文件选择并进入哈希步骤" in names
    finally:
        window.close()
        set_theme_mode("light")


def test_verifier_hash_columns_use_stable_mono_font(qapp):
    model = VerifierResultModel()
    model.set_results([{
        "path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc",
    }])

    for column in (model.COL_PATH, model.COL_EXPECTED, model.COL_ACTUAL):
        font = model.data(model.index(0, column), Qt.ItemDataRole.FontRole)
        assert font is not None
        assert font.family() == "Cascadia Mono"
        assert font.pointSize() == 12


def test_result_table_exposes_fluent_keyboard_focus_ring(qapp):
    for mode in ("light", "dark"):
        set_theme_mode(mode)
        stylesheet = generate_builder_stylesheet(mode)
        assert "QTableView:focus" in stylesheet
        assert "QTableView::item:focus" in stylesheet
        assert "2px solid" in stylesheet
