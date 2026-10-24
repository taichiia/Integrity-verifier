from PySide6.QtWidgets import QMessageBox

import verifier.main as verifier_main
from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import VerifierMainWindow


def test_verifier_applies_hash_batches(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)
    win = VerifierMainWindow({}, settings=settings)
    target = tmp_path / "target"
    target.mkdir()
    expected = {
        str(target / "a.txt"): "abc",
        str(target / "b.txt"): "xyz",
    }

    win._on_verify_files(
        [
            (str(target / "a.txt"), "abc", ""),
            (str(target / "b.txt"), "abc", ""),
            (str(target / "missing.txt"), "", "File not found"),
        ],
        expected,
        str(target),
    )

    statuses = {entry["path"]: entry["status"] for entry in win._all_results}
    assert statuses == {
        "a.txt": "pass",
        "b.txt": "fail",
        "missing.txt": "error",
    }
    win.close()
    set_theme_mode("light")


def test_protection_continue_defaults_to_exit(qapp, monkeypatch):
    answers = []

    def fake_question(parent, title, message, buttons, default):
        answers.append((title, message, default))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", fake_question)

    assert verifier_main._confirm_continue(None, "环境异常", "继续？") is False
    assert answers == [
        (
            "环境异常",
            "继续？",
            QMessageBox.StandardButton.No,
        )
    ]


def test_protection_high_risk_asks_user_to_continue(qapp, monkeypatch):
    class Assessment:
        level = "high_confidence"
        checks = []

    monkeypatch.setattr("shared.protection.run_vm_checks", lambda: [])
    monkeypatch.setattr("shared.protection.run_timing_check", lambda: [])
    monkeypatch.setattr(
        "shared.protection.assess_environment", lambda *args: Assessment()
    )
    monkeypatch.setattr(
        verifier_main,
        "_confirm_continue",
        lambda parent, title, message: title == "环境异常" and "是否仍要继续" in message,
    )

    result = verifier_main._run_protection_checks({
        "enable_antisanbox": True,
        "enable_antidebug": False,
    })

    assert result is True
