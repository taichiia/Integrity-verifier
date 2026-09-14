from PySide6.QtCore import Qt

from builder.ui.main_window import BuilderMainWindow
from builder.ui.widgets.file_table import FileTableModel
from shared.preferences import create_settings
from shared.theme import set_theme_mode
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


def test_verifier_hash_columns_use_stable_mono_font(qapp):
    model = VerifierResultModel()
    model.set_results([{
        "path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc",
    }])

    for column in (model.COL_PATH, model.COL_EXPECTED, model.COL_ACTUAL):
        font = model.data(model.index(0, column), Qt.ItemDataRole.FontRole)
        assert font is not None
        assert font.family() == "JetBrains Mono"
        assert font.pointSize() == 12
