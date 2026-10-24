from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from verifier.ui.main_window import VerifierResultModel


def test_model_has_actual_hash_column(qapp):
    model = VerifierResultModel()
    model.set_results([
        {"path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc"},
        {"path": "b.txt", "status": "fail", "expected": "abc", "actual": "xyz"},
        {"path": "c.txt", "status": "missing", "expected": "abc", "actual": ""},
    ])

    assert model.columnCount() == 4
    assert (model.headerData(3, Qt.Orientation.Horizontal,
                             Qt.ItemDataRole.DisplayRole) == "实际哈希值")
    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == "xyz"
    assert model.data(model.index(2, 3), Qt.ItemDataRole.DisplayRole) == ""


def test_model_tolerates_missing_actual_key(qapp):
    model = VerifierResultModel()
    model.set_results([{"path": "a.txt", "status": "pass", "expected": "abc"}])

    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == ""
    assert model.data(model.index(0, 3), Qt.ItemDataRole.ToolTipRole) == "实际: "


def test_verifier_status_has_icon_and_accessible_text(qapp):
    model = VerifierResultModel()
    model.set_results([
        {"path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc"},
        {"path": "b.txt", "status": "fail", "expected": "abc", "actual": "xyz"},
    ])

    for row, accessible_text in enumerate(("通过", "失败")):
        index = model.index(row, VerifierResultModel.COL_STATUS)
        icon = model.data(index, Qt.ItemDataRole.DecorationRole)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()
        assert model.data(index, Qt.ItemDataRole.AccessibleTextRole) == accessible_text
