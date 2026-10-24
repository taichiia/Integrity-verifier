import base64
import sys
import types

from PySide6.QtWidgets import QMessageBox

import shared.protection
import verifier.main as verifier_main
from builder.ui.workers.pack_worker import PackWorker
from shared.crypto import generate_rsa_keypair
from shared.protection import append_self_integrity, verify_self_integrity


def test_unsigned_self_integrity_detects_body_and_trailer_changes(
    tmp_path, monkeypatch,
):
    monkeypatch.setitem(sys.modules, "verifier._embedded_data", None)
    exe = tmp_path / "verifier.exe"
    exe.write_bytes(b"original verifier")
    append_self_integrity(str(exe))

    assert verify_self_integrity(str(exe)) == (True, "self integrity verified")

    body = bytearray(exe.read_bytes())
    body[3] = ord("X")
    exe.write_bytes(body)
    ok, detail = verify_self_integrity(str(exe))
    assert ok is False
    assert "self hash mismatch" in detail

    exe.write_bytes(exe.read_bytes() + b"extra")
    ok, detail = verify_self_integrity(str(exe))
    assert ok is False
    assert detail


def test_signed_self_integrity_uses_embedded_public_key(tmp_path, monkeypatch):
    keypair = generate_rsa_keypair()
    module = types.ModuleType("verifier._embedded_data")
    module.EMBEDDED_PUBLIC_KEY = base64.b64encode(
        keypair.public_pem
    ).decode("ascii")
    monkeypatch.setitem(
        __import__("sys").modules, "verifier._embedded_data", module
    )

    exe = tmp_path / "verifier.exe"
    exe.write_bytes(b"signed verifier")
    append_self_integrity(
        str(exe), keypair.private_pem.decode("ascii"), "RSA"
    )

    assert verify_self_integrity(str(exe)) == (True, "self integrity verified")

    body = bytearray(exe.read_bytes())
    body[0] = ord("X")
    exe.write_bytes(body)
    ok, detail = verify_self_integrity(str(exe))
    assert ok is False
    assert "self hash mismatch" in detail


def test_pack_worker_applies_self_integrity_with_project_key(monkeypatch):
    worker = PackWorker({})
    observed = {}

    def fake_append(path, private_key, algorithm):
        observed.update(path=path, key=private_key, algorithm=algorithm)

    monkeypatch.setattr("shared.protection.append_self_integrity", fake_append)
    worker._apply_self_integrity("verifier.exe")

    assert observed == {"path": "verifier.exe", "key": None, "algorithm": "RSA"}


def test_protection_check_failure_is_reported(monkeypatch, qapp):
    questions = []

    def fail_debugger_checks():
        raise RuntimeError("protection API unavailable")

    def fake_question(parent, title, message, buttons, default):
        questions.append((title, message, default))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(shared.protection, "run_debugger_checks", fail_debugger_checks)
    monkeypatch.setattr(verifier_main.QMessageBox, "question", fake_question)

    result = verifier_main._run_protection_checks({"enable_antidebug": True})

    assert result is False
    assert len(questions) == 1
    assert questions[0][0] == "保护检查异常"
    assert "protection API unavailable" in questions[0][1]
    assert questions[0][2] == QMessageBox.StandardButton.No
