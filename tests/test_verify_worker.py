import hashlib
import os
import tempfile

from builder.ui.workers.verify_worker import VerifyWorker


def _run_simulation(entries, target_dir, exclude_paths=None):
    reports = []
    worker = VerifyWorker(entries, target_dir, "sha256", exclude_paths=exclude_paths)
    worker.finished.connect(reports.append)
    worker.run()
    return reports[0]


def test_simulation_ignores_verifier_exe_at_target_root():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "target")
        os.makedirs(target)
        payload = b"payload"
        with open(os.path.join(target, "app.dll"), "wb") as f:
            f.write(payload)
        with open(os.path.join(target, "FileIntegrityVerifier.exe"), "wb") as f:
            f.write(b"verifier binary")
        entries = [{
            "path": "app.dll",
            "hash": hashlib.sha256(payload).hexdigest(),
            "status": "ok",
        }]

        report = _run_simulation(entries, target)

    assert report["passed"] == 1
    assert report["extra"] == []
    assert report["extra_count"] == 0


def test_simulation_flags_nested_verifier_copy_as_extra():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "target")
        nested = os.path.join(target, "old")
        os.makedirs(nested)
        payload = b"payload"
        with open(os.path.join(target, "app.dll"), "wb") as f:
            f.write(payload)
        with open(os.path.join(nested, "FileIntegrityVerifier.exe"), "wb") as f:
            f.write(b"stale copy")
        entries = [{
            "path": "app.dll",
            "hash": hashlib.sha256(payload).hexdigest(),
            "status": "ok",
        }]

        report = _run_simulation(entries, target)

    assert report["extra"] == ["old/FileIntegrityVerifier.exe"]
    assert report["extra_count"] == 1


def test_worker_excludes_custom_paths(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    payload = b"payload"
    (target / "app.dll").write_bytes(payload)
    stale = target / "old_tool.exe"
    stale.write_bytes(b"stale")
    entries = [{
        "path": "app.dll",
        "hash": hashlib.sha256(payload).hexdigest(),
        "status": "ok",
    }]

    report = _run_simulation(entries, str(target), exclude_paths=[str(stale)])

    assert report["extra"] == []
    assert report["passed"] == 1
