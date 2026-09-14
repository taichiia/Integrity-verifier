import json

from PySide6.QtWidgets import QFileDialog, QMessageBox

import builder.ui.main_window as builder_main_window
import builder.ui.step2_hashes as step2_hashes
from builder.ui.main_window import BuilderMainWindow
from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import VerifierMainWindow

from tests.test_step2_hashes import FakeHashWorker


def _wait_for(condition, timeout_ms=5000):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    elapsed = 0
    while not condition() and elapsed < timeout_ms:
        app.processEvents()
        elapsed += 10
    return condition()


def test_builder_hash_flow_actually_updates_manifest(qapp, tmp_path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")

    settings = create_settings(tmp_path / "settings.ini")
    window = BuilderMainWindow(settings=settings)
    try:
        window._step1.scan_directory(str(tmp_path))
        assert _wait_for(lambda: window._step1._worker is None)

        window._step1._file_table.model().select_all()
        window._step1._go_next()

        assert window._stack.currentIndex() == 1
        assert window._step2._manifest.toPlainText().count("PEND") == 2
        window._step2._start_btn.click()

        assert _wait_for(
            lambda: not window._step2._start_btn.isEnabled()
            or window._step2._manifest.toPlainText().count(" OK ") == 2
        )
        assert _wait_for(lambda: window._step2._start_btn.isEnabled())
        assert window._step2._manifest.toPlainText().count(" OK ") == 2
    finally:
        window.close()
        set_theme_mode("light")


def test_builder_hash_flow_reports_missing_files(qapp, tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "missing.txt").write_text("temporary", encoding="utf-8")
    monkeypatch.setattr(step2_hashes, "HashWorker", FakeHashWorker)

    settings = create_settings(tmp_path / "settings.ini")
    window = BuilderMainWindow(settings=settings)
    try:
        window._step1.scan_directory(str(tmp_path))
        assert _wait_for(lambda: window._step1._worker is None)
        window._step1._file_table.model().select_all()
        window._step1._go_next()

        window._step2._start_btn.click()
        window._step2._worker.file_done.emit(
            str(tmp_path / "missing.txt"), "", "File not found"
        )

        assert window._step2._manifest.toPlainText().count("ERR") == 1
    finally:
        window.close()
        set_theme_mode("light")


def test_verifier_exports_json_from_ui(qapp, tmp_path, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(report_path), "JSON 文件 (*.json)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window = VerifierMainWindow({}, settings=settings)
    try:
        target = tmp_path / "target"
        target.mkdir()
        window._target_path.setText(str(target))
        window._all_results = [
            {"path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc"},
            {"path": "b.txt", "status": "fail", "expected": "abc", "actual": "xyz"},
        ]

        window._export_report()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["target_path"] == str(target)
        assert report["summary"] == {
            "pass": 1, "fail": 1, "missing": 0, "extra": 0, "error": 0, "total": 2,
        }
    finally:
        window.close()
        set_theme_mode("light")


def test_verifier_json_export_cancel_keeps_no_report(qapp, tmp_path, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    window = VerifierMainWindow({}, settings=settings)
    try:
        window._all_results = [{
            "path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc",
        }]
        window._export_report()

        assert not (tmp_path / "report.json").exists()
    finally:
        window.close()
        set_theme_mode("light")


def test_builder_about_repo_button_opens_repository(qapp, tmp_path, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    opened = []
    monkeypatch.setattr(
        builder_main_window.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()),
    )
    window = BuilderMainWindow(settings=settings)
    try:
        box = window._create_about_box()
        repo_button = next(button for button in box.buttons() if button.text() == "打开仓库")
        repo_button.click()
        window._handle_about_result(box)

        assert opened == ["https://github.com/taichiia/Integrity-verifier"]
    finally:
        window.close()
        set_theme_mode("light")
