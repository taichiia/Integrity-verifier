from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import TargetPathEdit, VerifierMainWindow


class FakeDropEvent:
    def __init__(self, path: Path):
        self._mime = QMimeData()
        self._mime.setUrls([QUrl.fromLocalFile(str(path))])
        self._accepted = False

    def mimeData(self) -> QMimeData:
        return self._mime

    def acceptProposedAction(self) -> None:
        self._accepted = True

    def ignore(self) -> None:
        self._accepted = False

    def isAccepted(self) -> bool:
        return self._accepted


def _drop_event(path: Path) -> FakeDropEvent:
    return FakeDropEvent(path)


def test_target_edit_drag_accepts_directories_only(tmp_path, qapp):
    edit = TargetPathEdit()
    target = tmp_path / "target"
    target.mkdir()
    target_event = _drop_event(target)

    edit.dragEnterEvent(target_event)
    assert target_event.isAccepted()

    file_path = tmp_path / "file.txt"
    file_path.write_text("payload", encoding="utf-8")
    file_event = _drop_event(file_path)

    edit.dragEnterEvent(file_event)
    assert not file_event.isAccepted()


def test_target_edit_drop_sets_directory_path(tmp_path, qapp):
    edit = TargetPathEdit()
    target = tmp_path / "target"
    target.mkdir()
    event = _drop_event(target)

    edit.dropEvent(event)

    assert event.isAccepted()
    assert edit.text() == str(target)


def test_verifier_drop_updates_target_and_clears_results(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)

    win = VerifierMainWindow({}, settings=settings)
    target = tmp_path / "target"
    target.mkdir()
    win._all_results = [{"path": "old.dll", "status": "pass", "expected": "abc", "actual": "abc"}]
    win._verify_total = 1
    win._result_model.set_results(win._all_results)

    win._target_path.dropEvent(_drop_event(target))

    assert win._target_path.text() == str(target)
    assert win._all_results == []
    assert win._result_model.rowCount() == 0
    assert win._verify_total == 0

    win.close()
    set_theme_mode("light")
