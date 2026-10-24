import os

import build as build_script


def test_rust_build_copies_expected_artifacts(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "output"
    artifacts = {
        "Rust Builder": (str(target / "fit-builder.exe"), "FileIntegrityBuilderRust.exe"),
        "Rust Verifier": (str(target / "fit-verifier.exe"), "FileIntegrityVerifierRust.exe"),
        "Rust Record CLI": (str(target / "fit-rec.exe"), "fit-rec.exe"),
    }
    for source, _ in artifacts.values():
        with open(source, "wb") as handle:
            handle.write(b"rust exe")

    expected_commands = [
        ["cargo", "build", "--release", "-p", "fit-verifier", "-p", "fit-cli"],
        ["cargo", "build", "--release", "-p", "fit-builder"],
    ]

    def fake_cargo_build(args, **kwargs):
        assert args == expected_commands.pop(0)
        assert kwargs.get("cwd") == str(tmp_path)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(build_script, "ROOT", str(tmp_path))
    monkeypatch.setattr(build_script, "OUTPUT", str(output))
    monkeypatch.setattr(build_script, "RUST_ARTIFACTS", artifacts)
    monkeypatch.setattr(build_script.subprocess, "run", fake_cargo_build)

    results = build_script.build_rust()

    assert not expected_commands

    assert set(results) == {"Rust Builder", "Rust Verifier", "Rust Record CLI"}
    assert (output / "FileIntegrityBuilderRust.exe").exists()
    assert (output / "FileIntegrityVerifierRust.exe").exists()
    assert (output / "fit-rec.exe").exists()


def test_rust_build_reports_cargo_failure(tmp_path, monkeypatch):
    output = tmp_path / "output"

    def fake_cargo_build(args, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "cargo failed"

        return Result()

    monkeypatch.setattr(build_script, "ROOT", str(tmp_path))
    monkeypatch.setattr(build_script, "OUTPUT", str(output))
    monkeypatch.setattr(build_script.subprocess, "run", fake_cargo_build)

    assert build_script.build_rust() == {}
    assert not output.exists()
import build as build_script


def test_release_build_excludes_project_embedded_data(tmp_path, monkeypatch):
    embedded = tmp_path / "_embedded_data.py"
    embedded.write_text("EMBEDDED_CONFIG_B64 = 'project-secret'\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "EMBEDDED_DATA", str(embedded))

    with build_script.without_embedded_data():
        # The release build must not see (or bundle) the user's manifest.
        assert not embedded.exists()

    assert embedded.read_text(encoding="utf-8").startswith("EMBEDDED_CONFIG_B64")


def test_release_build_tolerates_missing_embedded_data(tmp_path, monkeypatch):
    monkeypatch.setattr(
        build_script, "EMBEDDED_DATA", str(tmp_path / "_embedded_data.py"),
    )

    with build_script.without_embedded_data():
        pass

    assert not (tmp_path / "_embedded_data.py").exists()


def test_cli_verifier_build_excludes_gui_stack(monkeypatch, tmp_path):
    captured = {}

    def fake_build_exe(entry, name, icon_path="", extra_args=None,
                       include_shared=True, console=False):
        captured.update(
            entry=entry,
            name=name,
            extra_args=extra_args or [],
            include_shared=include_shared,
            console=console,
        )
        return "output/FileIntegrityVerifierCLI.exe"

    monkeypatch.setattr(build_script, "EMBEDDED_DATA", str(tmp_path / "_embedded_data.py"))
    monkeypatch.setattr(build_script, "build_exe", fake_build_exe)

    result = build_script.build_cli_verifier()

    assert result == "output/FileIntegrityVerifierCLI.exe"
    assert captured["entry"].endswith(os.path.join("verifier", "cli.py"))
    assert captured["name"] == "FileIntegrityVerifierCLI"
    assert captured["console"] is True
    assert captured["include_shared"] is False
    assert "--exclude-module=PySide6" in captured["extra_args"]
    assert "--exclude-module=shiboken6" in captured["extra_args"]
