import json

from builder.ui.step2_hashes import Step2Hashes
from builder.ui.workers.pack_worker import PackWorker
from shared.project import ProjectData


def test_step2_batch_flush_updates_lines_without_full_rebuild(qapp, tmp_path):
    project = ProjectData(base_directory=str(tmp_path))
    project.checksum_entries = [
        {"path": f"file-{index:03d}.bin", "hash": "", "status": "pending"}
        for index in range(220)
    ]
    step = Step2Hashes(project)
    step.refresh_from_project()
    step._update_manifest()
    full_rebuilds = []
    step._update_manifest = lambda: full_rebuilds.append(True)

    step._is_running = True
    step._on_files_done([
        (f"file-{index:03d}.bin", f"digest-{index}", "")
        for index in range(220)
    ])
    step._flush_manifest_updates()

    assert full_rebuilds == []
    assert step._manifest.toPlainText().count("digest-") == 220
    assert step._pending_manifest_rows == set()


def test_pack_worker_writes_windows_version_resource(tmp_path):
    worker = PackWorker({
        "verifier_title": "发布验证器",
        "verifier_version": "2.3.10.4",
        "verifier_company": "Example Co",
        "verifier_copyright": "Copyright (C) 2026 Example Co",
    })
    version_file = tmp_path / "version.py"
    worker._write_version_file(str(version_file))

    contents = version_file.read_text(encoding="utf-8")
    assert "filevers=(2, 3, 10, 4)" in contents
    assert f"StringStruct('CompanyName', {json.dumps('Example Co')})" in contents
    assert f"StringStruct('LegalCopyright', {json.dumps('Copyright (C) 2026 Example Co')})" in contents
    assert f"StringStruct('ProductName', {json.dumps('发布验证器')})" in contents
