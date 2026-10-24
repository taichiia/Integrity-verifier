import base64
import hashlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

from shared.crypto import aes_encrypt, generate_aes_key
import verifier as verifier_pkg
from verifier import cli


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(verifier_pkg.__file__)))


def _install_embedded(monkeypatch, config=None, empty=False):
    module = types.ModuleType("verifier._embedded_data")
    if not empty:
        key = generate_aes_key()
        plaintext = json.dumps(config or {}, ensure_ascii=False).encode("utf-8")
        module.EMBEDDED_CONFIG_KEY = base64.b64encode(key).decode("ascii")
        module.EMBEDDED_CONFIG_B64 = base64.b64encode(
            aes_encrypt(plaintext, key)).decode("ascii")
    monkeypatch.setitem(sys.modules, "verifier._embedded_data", module)


def _make_target(tmp_path, payload=b"payload", corrupt=False, extra=False):
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.dll").write_bytes(b"tampered" if corrupt else payload)
    if extra:
        (target / "note.txt").write_bytes(b"extra")
    config = {
        "checksum_entries": [{
            "path": "app.dll",
            "hash": hashlib.sha256(payload).hexdigest(),
            "status": "ok",
        }],
        "algorithm": "sha256",
    }
    return target, config


def test_cli_success_exit_zero(tmp_path, monkeypatch, capsys):
    target, config = _make_target(tmp_path)
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target)])
    out = capsys.readouterr().out

    assert code == cli.EXIT_OK
    assert "[通过] app.dll" in out
    assert "汇总: 通过 1/1" in out


def test_cli_tampered_file_exit_one(tmp_path, monkeypatch, capsys):
    target, config = _make_target(tmp_path, corrupt=True)
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target)])
    out = capsys.readouterr().out

    assert code == cli.EXIT_VERIFY_FAILED
    assert "[失败] app.dll" in out


def test_cli_missing_file_exit_one(tmp_path, monkeypatch, capsys):
    target = tmp_path / "target"
    target.mkdir()
    config = {"checksum_entries": [
        {"path": "gone.dll", "hash": "x", "status": "ok"},
    ], "algorithm": "sha256"}
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target)])
    out = capsys.readouterr().out

    assert code == cli.EXIT_VERIFY_FAILED
    assert "[缺失] gone.dll" in out


def test_cli_extra_file_reported_and_failing(tmp_path, monkeypatch, capsys):
    target, config = _make_target(tmp_path, extra=True)
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target)])
    out = capsys.readouterr().out

    # Files the Builder filtered out never reach this list because the packed
    # ignore rules travel with the verifier; anything left is a real addition.
    assert code == cli.EXIT_VERIFY_FAILED
    assert "[多余] note.txt" in out


def test_cli_ignored_file_does_not_fail(tmp_path, monkeypatch, capsys):
    target, config = _make_target(tmp_path, extra=True)
    config["exclude_rules"] = {
        "rule_version": 1,
        "enabled": True,
        "blacklist": True,
        "extensions": ["txt"],
        "folders": [],
        "min_size": 0,
        "max_size": 0,
    }
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target)])
    out = capsys.readouterr().out

    assert code == cli.EXIT_OK
    assert "[多余]" not in out


def test_cli_writes_report_file(tmp_path, monkeypatch):
    target, config = _make_target(tmp_path)
    _install_embedded(monkeypatch, config)
    report_path = tmp_path / "verify-report.json"

    code = cli.main([
        "--target", str(target), "--report", str(report_path),
    ])

    assert code == cli.EXIT_OK
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] == 1
    assert report["extra_count"] == 0


def test_main_dispatches_target_flag_to_cli(tmp_path):
    """A --target run must use the CLI instead of opening the GUI."""
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "verifier", "main.py"),
         "--target", str(tmp_path)],
        capture_output=True, text=True, encoding="cp936",
        cwd=REPO_ROOT, timeout=120,
    )

    # A GUI run would block forever; the CLI path always terminates with one of
    # the documented exit codes and prints either a report or an error.
    assert result.returncode in (
        cli.EXIT_OK, cli.EXIT_VERIFY_FAILED, cli.EXIT_NO_DATA, cli.EXIT_BAD_TARGET,
    )
    assert "汇总" in result.stdout or "错误" in result.stdout or "警告" in result.stderr or "无校验数据" in result.stderr


def test_cli_json_output(tmp_path, monkeypatch, capsys):
    target, config = _make_target(tmp_path)
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(target), "--json"])
    out = capsys.readouterr().out

    report = json.loads(out)
    assert code == cli.EXIT_OK
    assert report["passed"] == 1
    assert report["total"] == 1
    assert report["details"][0]["actual"]


def test_cli_bad_target_exit_three(tmp_path, monkeypatch, capsys):
    config = {"checksum_entries": [
        {"path": "app.dll", "hash": "x", "status": "ok"},
    ], "algorithm": "sha256"}
    _install_embedded(monkeypatch, config)

    code = cli.main(["--target", str(tmp_path / "nope")])
    err = capsys.readouterr().err

    assert code == cli.EXIT_BAD_TARGET
    assert "目标目录不存在" in err


def test_cli_invalid_algorithm_fails_once(tmp_path, monkeypatch, capsys):
    code = cli.main([
        "--target", str(tmp_path), "--algorithm", "sha999",
    ])
    err = capsys.readouterr().err

    assert code == cli.EXIT_BAD_ALGORITHM
    assert "不支持的哈希算法: sha999" in err


def test_cli_selects_embedded_checklist(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.dll").write_bytes(b"payload")
    config = {
        "checksum_entries": [{
            "path": "app.dll",
            "hash": hashlib.sha256(b"payload").hexdigest(),
            "status": "ok",
        }],
        "checklists": {
            "one": [{
                "path": "app.dll",
                "hash": hashlib.sha256(b"payload").hexdigest(),
                "status": "ok",
            }],
            "two": [{
                "path": "other.dll",
                "hash": "0" * 64,
                "status": "ok",
            }],
        },
        "algorithm": "sha256",
    }
    _install_embedded(monkeypatch, config)

    assert cli.main(["--target", str(target), "--checklist", "one"]) == cli.EXIT_OK
    assert cli.main(["--target", str(target), "--checklist", "two"]) == cli.EXIT_VERIFY_FAILED
    assert cli.main(["--target", str(target), "--checklist", "missing"]) == cli.EXIT_BAD_CHECKLIST


def test_cli_no_embedded_data_exit_two(tmp_path, monkeypatch, capsys):
    _install_embedded(monkeypatch, empty=True)

    code = cli.main(["--target", str(tmp_path)])
    err = capsys.readouterr().err

    assert code == cli.EXIT_NO_DATA
    assert "无校验数据" in err


def test_cli_help_smoke():
    result = subprocess.run(
        [sys.executable, "-m", "verifier.cli", "--help"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert "--target" in result.stdout


def test_cli_subprocess_end_to_end(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    payload = b"payload"
    (target / "app.dll").write_bytes(payload)
    config = {
        "title": "test", "version": "1.0",
        "checksum_entries": [{
            "path": "app.dll",
            "hash": hashlib.sha256(payload).hexdigest(),
            "status": "ok",
        }],
        "algorithm": "sha256",
        "path_rule": "current_dir",
    }
    key = generate_aes_key()
    plaintext = json.dumps(config, ensure_ascii=False).encode("utf-8")
    content = "\n".join([
        "# Auto-generated embedded data for File Integrity Verifier",
        "# DO NOT EDIT MANUALLY",
        f"EMBEDDED_CONFIG_KEY = {json.dumps(base64.b64encode(key).decode('ascii'))}",
        f"EMBEDDED_CONFIG_B64 = {json.dumps(base64.b64encode(aes_encrypt(plaintext, key)).decode('ascii'))}",
    ])
    embedded_path = Path(verifier_pkg.__file__).parent / "_embedded_data.py"
    original = embedded_path.read_bytes() if embedded_path.exists() else None
    try:
        embedded_path.write_text(content, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "verifier.cli", "--target", str(target)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == cli.EXIT_OK, result.stderr
        assert "[通过] app.dll" in result.stdout
    finally:
        if original is None:
            embedded_path.unlink(missing_ok=True)
        else:
            embedded_path.write_bytes(original)
