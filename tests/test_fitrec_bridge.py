from builder.ui.step3_pack import Step3Pack
from builder.ui.workers.pack_worker import PackWorker
from shared.fitrec_bridge import (
    build_fit_document,
    fitrec_tool_path,
    run_fitrec_generate,
    run_fitrec_keygen,
)
from shared.project import ProjectData


def test_build_fit_document_selects_active_list_and_rules():
    entries = [{"path": "app.dll", "hash": "hash-a", "status": "ok"}]
    document = build_fit_document(
        {"release": entries, "legacy": []},
        "release",
        "sha256",
        ["logs"],
        {"enabled": True, "extensions": ["log"]},
    )

    assert document["format_version"] == 1
    assert document["active_checklist"] == "release"
    assert document["checklists"]["release"] == entries
    assert document["exclude_paths"] == ["logs"]
    assert document["exclude_rules"] == {"enabled": True, "extensions": ["log"]}


def test_fitrec_tool_is_available_and_bridge_creates_record(tmp_path):
    tool = fitrec_tool_path()
    assert tool.is_file(), f"fit-rec tool missing: {tool}"

    private_key = tmp_path / "fitrec.key"
    public_key = tmp_path / "fitrec.pub"
    run_fitrec_keygen(str(private_key), str(public_key))

    entries = [
        {"path": "app.dll", "hash": "hash-a", "size": 12, "status": "ok"},
        {"path": "data/asset.bin", "hash": "hash-b", "size": 34, "status": "ok"},
    ]
    document = build_fit_document(
        {"release": entries},
        "release",
        "sha256",
        ["logs"],
        {},
    )
    assert document == {
        "format_version": 1,
        "algorithm": "sha256",
        "active_checklist": "release",
        "checklists": {"release": entries},
        "exclude_paths": ["logs"],
        "exclude_rules": {},
        "metadata": {},
    }
    record = tmp_path / "FileIntegrityVerifier.fitrec"
    run_fitrec_generate(document, str(record), str(private_key), 8, 4)

    assert record.is_file()
    assert (tmp_path / "FileIntegrityVerifier.fitrec.pub").is_file()
    assert record.read_bytes()[:8] == b"FITREC1\0"


def test_keygen_and_generation_do_not_overwrite_private_key(tmp_path):
    private_key = tmp_path / "fitrec.key"
    public_key = tmp_path / "fitrec.pub"
    run_fitrec_keygen(str(private_key), str(public_key))

    try:
        run_fitrec_keygen(str(private_key), str(public_key))
    except RuntimeError as error:
        assert "私钥已存在" in str(error)
    else:
        raise AssertionError("keygen unexpectedly overwrote an existing key")


def test_step3_persists_fitrec_settings(qapp):
    project = ProjectData(
        generate_fitrec=True,
        fitrec_private_key_path="C:/private/fitrec.key",
        fitrec_data_shards=10,
        fitrec_parity_shards=6,
    )
    step = Step3Pack(project)

    step._fitrec_cb.setChecked(False)
    step._fitrec_key_edit.setText("D:/new/fitrec.key")
    step._fitrec_data_spin.setValue(12)
    step._fitrec_parity_spin.setValue(8)
    step.sync_to_project()

    assert project.generate_fitrec is False
    assert project.fitrec_private_key_path == "D:/new/fitrec.key"
    assert project.fitrec_data_shards == 12
    assert project.fitrec_parity_shards == 8

    step.refresh_from_project()
    assert step._fitrec_cb.isChecked() is False
    assert step._fitrec_data_spin.value() == 12
    assert step._fitrec_parity_spin.value() == 8
    step.deleteLater()


def test_pack_worker_generates_recovery_record(tmp_path):
    private_key = tmp_path / "fitrec.key"
    public_key = tmp_path / "fitrec.pub"
    run_fitrec_keygen(str(private_key), str(public_key))
    entries = [
        {"path": "app.dll", "hash": "hash-a", "size": 12, "status": "ok"},
        {"path": "data/asset.bin", "hash": "hash-b", "size": 34, "status": "ok"},
    ]
    project = {
        "checksum_entries": entries,
        "checksum_algorithm": "sha256",
        "verifier_checklists": {"release": entries},
        "verifier_active_checklist": "release",
        "exclude_paths": ["logs"],
        "exclude_rules": {"enabled": True, "extensions": ["log"]},
        "generate_fitrec": True,
        "fitrec_private_key_path": str(private_key),
        "fitrec_data_shards": 8,
        "fitrec_parity_shards": 4,
    }
    exe_path = tmp_path / "FileIntegrityVerifier.exe"
    record_path = tmp_path / "FileIntegrityVerifier.fitrec"

    PackWorker(project)._generate_fitrec(str(exe_path))

    assert record_path.is_file()
    assert record_path.read_bytes()[:8] == b"FITREC1\0"
    assert (tmp_path / "FileIntegrityVerifier.fitrec.pub").is_file()
