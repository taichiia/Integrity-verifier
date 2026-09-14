from PySide6.QtWidgets import QMessageBox

from builder.ui.main_window import BuilderMainWindow
from shared.preferences import (
    create_settings,
    load_theme_mode,
    save_theme_mode,
)
from shared.theme import get_theme_mode, set_theme_mode
from verifier.ui.main_window import VerifierMainWindow


def test_theme_mode_roundtrip(tmp_path):
    settings = create_settings(tmp_path / "settings.ini")
    assert load_theme_mode(settings) == "light"

    save_theme_mode(settings, "dark")
    settings.sync()

    assert load_theme_mode(create_settings(tmp_path / "settings.ini")) == "dark"


def test_invalid_theme_mode_falls_back_to_light(tmp_path):
    settings = create_settings(tmp_path / "settings.ini")
    settings.setValue("ui/theme_mode", "neon")
    settings.sync()

    assert load_theme_mode(create_settings(tmp_path / "settings.ini")) == "light"


def test_builder_restores_theme_and_geometry(tmp_path, qapp):
    settings = create_settings(tmp_path / "settings.ini")
    win = BuilderMainWindow(settings=settings)
    win._toggle_theme()
    win.resize(1250, 750)
    win.close()

    restored = BuilderMainWindow(settings=settings)
    assert get_theme_mode() == "dark"
    assert restored.width() == 1250
    assert restored.height() == 750
    restored.close()
    set_theme_mode("light")


def test_verifier_restores_theme_and_geometry(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    settings = create_settings(tmp_path / "settings.ini")
    save_theme_mode(settings, "dark")

    win = VerifierMainWindow({}, settings=settings)
    win.resize(1200, 700)
    win.close()

    restored = VerifierMainWindow({}, settings=settings)
    assert get_theme_mode() == "dark"
    assert restored.width() == 1200
    assert restored.height() == 700
    restored.close()
    set_theme_mode("light")
