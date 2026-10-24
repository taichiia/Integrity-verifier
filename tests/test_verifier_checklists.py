import hashlib
import json
import base64
import zlib

from builder.ui.workers.pack_worker import PackWorker
from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import VerifierMainWindow
from shared.crypto import aes_decrypt


def _entry(path: str, digest: str) -> dict:
    return {"path": path, "hash": digest, "status": "ok"}


def test_pack_worker_embeds_active_checklist(tmp_path):
    default_entries = [_entry("a.dll", "hash-a")]
    second_entries = [_entry("b.dll", "hash-b")]
    project = {
        "checksum_entries": second_entries,
        "verifier_checklists": {
            "default": default_entries,
            "second": second_entries,
        },
        "verifier_active_checklist": "second",
        "exclude_paths": ["vendor.dat"],
        "verifier_embed_encrypted": True,
    }
    output = tmp_path / "_embedded_data.py"

    PackWorker(project)._write_embedded_data(str(output))

    key_line = next(
        line for line in output.read_text(encoding="utf-8").splitlines()
        if line.startswith("EMBEDDED_CONFIG_KEY = ")
    )
    payload_line = next(
        line for line in output.read_text(encoding="utf-8").splitlines()
        if line.startswith("EMBEDDED_CONFIG_B64 = ")
    )
    key = json.loads(key_line.split("=", 1)[1])
    payload = json.loads(payload_line.split("=", 1)[1])
    plaintext = aes_decrypt(base64.b64decode(payload), base64.b64decode(key))
    try:
        plaintext = zlib.decompress(plaintext)
    except zlib.error:
        pass
    config = json.loads(plaintext)
    manifest_bytes = json.dumps(
        sorted(second_entries, key=lambda entry: entry.get("path", "")),
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")

    assert config["checksum_entries"] == second_entries
    assert config["checklists"] == {
        "default": default_entries,
        "second": second_entries,
    }
    assert config["active_checklist"] == "second"
    assert config["exclude_paths"] == ["vendor.dat"]
    assert config["manifest_hash"] == hashlib.sha256(manifest_bytes).hexdigest()


def test_verifier_switches_checklists(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)

    default_entries = [_entry("a.dll", "hash-a")]
    second_entries = [_entry("b.dll", "hash-b")]
    config = {
        "checklists": {
            "default": default_entries,
            "second": second_entries,
        },
        "active_checklist": "second",
        "checksum_entries": second_entries,
    }

    win = VerifierMainWindow(config, settings=settings)
    assert win._checklist_combo.count() == 2
    assert win._checklist_combo.currentText() == "second"
    assert config["checksum_entries"] == second_entries

    win._checklist_combo.setCurrentText("default")

    assert config["checksum_entries"] == default_entries
    assert config["active_checklist"] == "default"
    assert win._all_results == []
    assert win._result_model.rowCount() == 0

    win.close()
    set_theme_mode("light")
