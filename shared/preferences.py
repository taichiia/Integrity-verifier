from pathlib import Path

from PySide6.QtCore import QSettings


def create_settings(settings_file: str | Path | None = None) -> QSettings:
    if settings_file is not None:
        return QSettings(str(settings_file), QSettings.Format.IniFormat)
    return QSettings("taichiia", "FileIntegrityTool")


def load_theme_mode(settings: QSettings) -> str:
    mode = settings.value("ui/theme_mode", "")
    return mode if mode in {"light", "dark"} else "light"


def save_theme_mode(settings: QSettings, mode: str) -> None:
    settings.setValue("ui/theme_mode", "dark" if mode == "dark" else "light")
    settings.sync()


def restore_window_geometry(window, settings: QSettings, window_key: str) -> None:
    geometry = settings.value(f"ui/{window_key}/geometry")
    if geometry:
        window.restoreGeometry(geometry)


def save_window_geometry(window, settings: QSettings, window_key: str) -> None:
    settings.setValue(f"ui/{window_key}/geometry", window.saveGeometry())
    settings.sync()
