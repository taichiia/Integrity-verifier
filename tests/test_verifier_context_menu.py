import os

from PySide6.QtWidgets import QApplication

from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import VerifierMainWindow


def test_copy_full_path_uses_target_directory(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)

    win = VerifierMainWindow({}, settings=settings)
    target = tmp_path / "target"
    target.mkdir()
    win._target_path.setText(str(target))
    win._result_model.set_results([
        {"path": "app.dll", "status": "pass", "expected": "abc", "actual": "abc"},
    ])

    class FakeClipboard:
        def __init__(self):
            self.text_value = ""

        def setText(self, value: str) -> None:
            self.text_value = value

    fake_clipboard = FakeClipboard()
    monkeypatch.setattr(QApplication, "clipboard", lambda: fake_clipboard)

    win._copy_full_path(0)

    expected = os.path.join(str(target), "app.dll")
    assert fake_clipboard.text_value == expected

    win.close()
    set_theme_mode("light")
