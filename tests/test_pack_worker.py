import sys
import os
import base64
import json
import hashlib
import types
import zlib

import builder.ui.workers.pack_worker as pack_worker
from builder.ui.workers.pack_worker import PackWorker, resolve_hooks_dir
from shared.crypto import (
    aes_decrypt, create_signed_payload, generate_rsa_keypair,
    verify_signed_payload,
)
from verifier.embedded import manifest_mismatch_message


def test_frozen_pyinstaller_run_uses_in_process_isolated_flag(qapp, monkeypatch):
    observed = []

    def fake_run(pyi_args):
        observed.append(getattr(sys, "_pyi_isolated_subprocess", False))

    monkeypatch.setattr(pack_worker, "run_pyinstaller", fake_run)
    worker = PackWorker({})

    sys.frozen = True
    try:
        worker._run_pyinstaller_in_process([])
    finally:
        sys.frozen = False

    assert observed == [True]
    assert getattr(sys, "_pyi_isolated_subprocess", False) is False


def test_hooks_dir_points_at_repo_build_hooks():
    hooks_dir = resolve_hooks_dir()

    assert os.path.basename(hooks_dir) == "build_hooks"
    # The Qt trimming hooks must be found, otherwise packed verifiers keep
    # Qt6Quick/Qt6Qml/opengl32sw and grow by ~17 MB.
    assert os.path.isdir(hooks_dir)
    assert os.path.isfile(os.path.join(hooks_dir, "hook-PySide6.py"))


def test_frozen_hooks_dir_uses_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    try:
        assert resolve_hooks_dir() == os.path.join(str(tmp_path), "build_hooks")
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)


def test_large_embedded_config_is_compressed(tmp_path):
    entries = [
        {
            "path": f"release/component-{index:03d}/library-{index:03d}.dll",
            "hash": "0" * 64,
            "status": "ok",
        }
        for index in range(100)
    ]
    project = {
        "checksum_entries": entries,
        "verifier_checklists": {"default": entries},
        "verifier_active_checklist": "default",
        "exclude_paths": ["vendor/cache.bin"],
        "verifier_embed_encrypted": True,
    }
    output = tmp_path / "_embedded_data.py"

    PackWorker(project)._write_embedded_data(str(output))

    namespace = {}
    exec(compile(output.read_text(encoding="utf-8"), str(output), "exec"), namespace)
    plaintext = aes_decrypt(
        base64.b64decode(namespace["EMBEDDED_CONFIG_B64"]),
        base64.b64decode(namespace["EMBEDDED_CONFIG_KEY"]),
    )
    try:
        plaintext = zlib.decompress(plaintext)
    except zlib.error:
        raise AssertionError("large embedded config was not compressed")
    config = json.loads(plaintext)

    assert config["checksum_entries"] == entries
    assert config["exclude_paths"] == ["vendor/cache.bin"]


def test_pack_worker_embeds_signed_manifest(tmp_path):
    entries = [
        {"path": "app.dll", "hash": "hash-a", "status": "ok"},
        {"path": "data.bin", "hash": "hash-b", "status": "ok"},
    ]
    keypair = generate_rsa_keypair()
    project = {
        "checksum_entries": entries,
        "verifier_checklists": {"default": entries},
        "verifier_active_checklist": "default",
        "verifier_enable_signature_verify": True,
        "signature_algorithm": "RSA",
        "public_key_pem": keypair.public_pem.decode("utf-8"),
        "private_key_pem": keypair.private_pem.decode("utf-8"),
    }
    output = tmp_path / "_embedded_data.py"

    PackWorker(project)._write_embedded_data(str(output))

    namespace = {}
    exec(compile(output.read_text(encoding="utf-8"), str(output), "exec"), namespace)
    decoded = verify_signed_payload(
        base64.b64decode(namespace["EMBEDDED_MANIFEST_SIGNATURE"]),
        base64.b64decode(namespace["EMBEDDED_PUBLIC_KEY"]),
    )

    import hashlib
    manifest_hash = hashlib.sha256(json.dumps(
        sorted(entries, key=lambda entry: entry.get("path", "")),
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")).hexdigest()
    assert decoded == {"manifest_hash": manifest_hash}


def test_verifier_rejects_bad_manifest_signature(monkeypatch):
    entries = [{"path": "app.dll", "hash": "hash-a", "status": "ok"}]
    manifest_hash = hashlib.sha256(json.dumps(
        sorted(entries, key=lambda entry: entry.get("path", "")),
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")).hexdigest()
    keypair = generate_rsa_keypair()
    signature = create_signed_payload(
        {"manifest_hash": "0" * 64},
        keypair.private_pem,
        "RSA",
    )
    module = types.ModuleType("verifier._embedded_data")
    module.EMBEDDED_PUBLIC_KEY = base64.b64encode(
        keypair.public_pem
    ).decode("ascii")
    module.EMBEDDED_MANIFEST_SIGNATURE = base64.b64encode(
        signature
    ).decode("ascii")
    monkeypatch.setitem(sys.modules, "verifier._embedded_data", module)

    message = manifest_mismatch_message({
        "checksum_entries": entries,
        "manifest_hash": manifest_hash,
        "enable_signature_verify": True,
    })

    assert message == "内嵌校验清单签名验证失败。数据可能已被篡改。"
