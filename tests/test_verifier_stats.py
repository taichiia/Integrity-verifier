import time

from PySide6.QtWidgets import QMessageBox

from verifier.ui.main_window import VerifierMainWindow, format_verify_stats


def test_format_verify_stats_with_files():
    assert format_verify_stats(2.0, 10) == "用时 2.0 秒 · 5.0 文件/秒"


def test_format_verify_stats_zero_total():
    assert format_verify_stats(1.5, 0) == "用时 1.5 秒"


def test_format_verify_stats_zero_elapsed():
    assert format_verify_stats(0.0, 10) == "用时 0.0 秒 · 0.0 文件/秒"


def test_verify_done_updates_speed_label(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    win = VerifierMainWindow({})
    win._verify_started_at = time.perf_counter() - 2.0
    win._verify_total = 10

    win._on_verify_done()

    text = win._speed_label.text()
    assert "用时" in text
    assert "文件/秒" in text
