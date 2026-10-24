import hashlib
import threading

import shared.verification as verification_module
from shared.hashing import HashCancelled
from shared.file_rules import FileRules
from shared.verification import run_verification


def test_parallel_verification_keeps_progress_and_details_contract(tmp_path):
    paths = []
    for index in range(8):
        path = tmp_path / f"file-{index}.txt"
        path.write_bytes(f"payload-{index}".encode("utf-8"))
        paths.append(path)

    entries = [
        {
            "path": path.name,
            "hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
    ]
    progress = []
    results = []

    report = run_verification(
        entries,
        str(tmp_path),
        "sha256",
        progress_callback=lambda completed, total, path: progress.append(
            (completed, total)
        ),
        result_callback=lambda path, index, status, total: results.append(
            (index, status)
        ),
    )

    assert report["passed"] == 8
    assert report["failed"] == 0
    assert report["missing"] == 0
    assert progress == [(index + 1, 8) for index in range(8)]
    assert sorted(results) == [(index, "pass") for index in range(8)]
    assert [detail["path"] for detail in report["details"]] == [
        f"file-{index}.txt" for index in range(8)
    ]


def test_cancelled_verification_does_not_report_hash_as_error(tmp_path, monkeypatch):
    path = tmp_path / "file.txt"
    path.write_bytes(b"payload")
    entries = [{"path": "file.txt", "hash": "digest"}]

    def cancel_immediately(filepath, algorithm, cancel_event=None):
        cancel_event.set()
        raise HashCancelled()

    monkeypatch.setattr(
        verification_module, "hash_file", cancel_immediately
    )

    report = run_verification(
        entries, str(tmp_path), "sha256", cancel_event=threading.Event(),
    )

    assert report["passed"] == 0
    assert report["failed"] == 0
    assert report["missing"] == 0
    assert report["details"] == []


def test_disabled_filters_do_not_stat_extra_candidates(tmp_path, monkeypatch):
    path = tmp_path / "file.txt"
    path.write_bytes(b"payload")

    def unexpected_size(path):
        raise AssertionError("disabled filters must not stat every candidate")

    monkeypatch.setattr(verification_module, "_safe_size", unexpected_size)

    report = run_verification(
        [{"path": "file.txt", "hash": "digest"}],
        str(tmp_path),
        "sha256",
        exclude_rules=FileRules(enabled=False),
    )

    assert report["total"] == 1
