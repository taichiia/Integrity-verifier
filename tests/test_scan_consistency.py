import os
import time

from PySide6.QtCore import Qt

from shared.file_rules import FileRules
from shared.hashing import hash_file
from shared.project import ProjectData
from builder.ui.step1_files import Step1Files
from builder.ui.step3_pack import Step3Pack
from builder.ui.workers.scan_worker import ScanWorker
from builder.ui.workers.verify_worker import VerifyWorker


def _scan(directory):
    found = []
    completions = []
    worker = ScanWorker([directory])
    worker.files_found.connect(
        lambda entries: found.extend(path for path, _, _ in entries)
    )
    worker.scan_complete.connect(
        lambda total, skipped: completions.append((total, skipped))
    )
    worker.run()
    return found, completions


def test_scan_collects_files_that_filters_would_hide(qapp, tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("js", encoding="utf-8")
    (tmp_path / "debug.log").write_text("log", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.dll").write_text("dll", encoding="utf-8")

    found, completions = _scan(str(tmp_path))

    relative = sorted(os.path.relpath(path, tmp_path) for path in found)
    assert relative == [
        os.path.join(".git", "config"),
        "debug.log",
        os.path.join("node_modules", "pkg.js"),
        os.path.join("src", "app.dll"),
    ]
    assert completions == [(4, 0)]


def test_step1_filter_whitelist_keeps_nested_folder_files(qapp, tmp_path):
    nested = tmp_path / "src" / "assets"
    nested.mkdir(parents=True)
    keep = nested / "logo.png"
    keep.write_bytes(b"png")
    drop = tmp_path / "src" / "app.py"
    drop.write_bytes(b"py")

    project = ProjectData(
        base_directory=str(tmp_path),
        file_paths=[str(keep), str(drop)],
        filter_enabled=True,
        filter_blacklist=False,
        filter_folders=["assets"],
    )
    step = Step1Files(project)
    step.refresh_from_project()

    assert [f["path"] for f in step._file_table.model().get_all()] == [str(keep)]

    # Disabling the filter must bring the hidden file back, which is only
    # possible because the scan kept the complete file list.
    project.filter_enabled = False
    step.refresh_from_project()

    assert len(step._file_table.model().get_all()) == 2
    step.deleteLater()


def test_step1_collapses_duplicate_paths(qapp, tmp_path):
    target = tmp_path / "app.dll"
    target.write_bytes(b"data")

    project = ProjectData(base_directory=str(tmp_path))
    step = Step1Files(project)

    step._on_files_found([
        (str(target), 4, 1704067200.0),
        (str(target), 4, 1704067200.0),
    ])
    step._on_files_dropped([str(target), str(target).upper()])

    assert step._file_table.model().rowCount() == 1
    assert len(step._all_files) == 1
    step.deleteLater()


def test_step1_persists_manual_exclusions(qapp, tmp_path):
    first = tmp_path / "app.dll"
    second = tmp_path / "vendor.dat"
    first.write_bytes(b"app")
    second.write_bytes(b"vendor")

    project = ProjectData(base_directory=str(tmp_path), filter_enabled=False)
    step = Step1Files(project)
    step._on_files_found([
        (str(first), 3, first.stat().st_mtime),
        (str(second), 6, second.stat().st_mtime),
    ])
    step._file_table.model().select_none()
    step._file_table.model().setData(
        step._file_table.model().index(0, 0),
        Qt.CheckState.Checked,
        Qt.ItemDataRole.CheckStateRole,
    )

    step.sync_to_project()

    assert [entry["path"] for entry in project.checksum_entries] == ["app.dll"]
    assert project.file_paths == [str(first), str(second)]
    assert project.exclude_paths == ["vendor.dat"]
    step.deleteLater()


def test_verify_worker_emits_report_once(qapp, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.dll").write_bytes(b"payload")

    reports = []
    worker = VerifyWorker([], str(target), "sha256")
    worker.completed.connect(reports.append)
    worker.start()
    worker.wait(5000)

    for _ in range(100):
        qapp.processEvents()
        if reports:
            break
        time.sleep(0.01)

    assert len(reports) == 1
    assert reports[0]["extra"] == ["app.dll"]
    assert reports[0]["errors"] == []


def test_step3_extra_files_block_packing(qapp):
    entry = {"path": "app.dll", "hash": "abc", "status": "ok"}
    project = ProjectData(
        checksum_entries=[dict(entry)],
        verifier_checklists={"default": [dict(entry)]},
        verifier_active_checklist="default",
    )
    step = Step3Pack(project)

    step._on_sim_finished({
        "total": 1,
        "passed": 1,
        "failed": 0,
        "missing": 0,
        "extra_count": 1,
        "extra": ["leftover.log"],
        "details": [{
            "path": "leftover.log",
            "status": "extra",
            "expected": "",
            "actual": "",
        }],
    })

    assert step._sim_passed is False
    assert not step._pack_btn.isEnabled()
    assert "EXTRA" in step._sim_detail.toPlainText()

    step._on_sim_finished({
        "total": 1,
        "passed": 1,
        "failed": 0,
        "missing": 0,
        "extra_count": 0,
        "extra": [],
        "details": [],
    })

    assert step._sim_passed is True
    assert step._pack_btn.isEnabled()
    step.deleteLater()


def test_switching_checklist_loads_its_entries(qapp):
    first = {"path": "a.dll", "hash": "hash-a", "status": "ok"}
    second = {"path": "b.dll", "hash": "hash-b", "status": "ok"}
    project = ProjectData(
        checksum_entries=[dict(first)],
        verifier_checklists={
            "default": [dict(first)],
            "second": [dict(second)],
        },
        verifier_active_checklist="default",
    )
    step = Step3Pack(project)
    step.refresh_from_project()

    assert step._checklist_combo.currentText() == "default"
    step._checklist_combo.setCurrentText("second")

    assert project.verifier_active_checklist == "second"
    assert project.checksum_entries == [second]
    # The entries that were active before the switch stay with their checklist.
    assert project.verifier_checklists["default"] == [first]
    step.deleteLater()


def test_loading_a_project_rebinds_every_step(qapp, tmp_path):
    from builder.ui.main_window import BuilderMainWindow
    from shared.preferences import create_settings

    settings = create_settings(tmp_path / "settings.ini")
    window = BuilderMainWindow(settings=settings)
    window._project.checksum_entries = [
        {"path": "a.dll", "hash": "abc", "status": "ok"}
    ]
    window._step2._checksum_entries = window._project.checksum_entries

    window._new_project()

    assert window._step1._project is window._project
    assert window._step2._project is window._project
    assert window._step3._project is window._project
    assert window._project.checksum_entries == []
    window.close()


def _build_manifest(step, found):
    # Load the project's filter rules into the panel, exactly like the UI does
    # when a project is opened or a step is revisited.
    step.refresh_from_project()
    scanned = []
    for path in found:
        stat = os.stat(path)
        scanned.append((path, stat.st_size, stat.st_mtime))
    step._on_files_found(scanned)
    step._on_scan_complete(len(found), 0)
    step.sync_to_project()
    base = step._project.base_directory
    entries = []
    for entry in step._project.checksum_entries:
        full = os.path.join(base, entry["path"])
        entries.append({
            "path": entry["path"],
            "hash": hash_file(full, "sha256"),
            "status": "ok",
        })
    return entries


def _verify(entries, target, rules):
    reports = []
    worker = VerifyWorker(
        entries, target, "sha256", exclude_rules=rules,
    )
    worker.completed.connect(reports.append)
    worker.run()
    return reports[0]


def test_ignored_files_are_not_reported_as_extra(qapp, tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("js", encoding="utf-8")
    (tmp_path / "debug.log").write_text("log", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sub.bin").write_bytes(b"bin")
    (tmp_path / "app.dll").write_bytes(b"dll")

    project = ProjectData(
        base_directory=str(tmp_path),
        filter_enabled=True,
        filter_blacklist=True,
        filter_extensions=["log"],
        filter_folders=[".git", "node_modules"],
    )
    step = Step1Files(project)
    found, completions = _scan(str(tmp_path))
    assert completions == [(5, 0)]

    entries = _build_manifest(step, found)

    assert sorted(e["path"].replace("\\", "/") for e in entries) == [
        "app.dll", "data/sub.bin",
    ]

    report = _verify(entries, str(tmp_path), FileRules.from_project(project))

    # Nothing changed on disk, so the filtered files must not surface as extra.
    assert report["extra"] == []
    assert report["extra_count"] == 0
    assert report["passed"] == 2
    assert report["failed"] == 0
    assert report["missing"] == 0
    step.deleteLater()


def test_whitelist_rules_still_report_unlisted_files(qapp, tmp_path):
    assets = tmp_path / "src" / "assets"
    assets.mkdir(parents=True)
    (assets / "logo.png").write_bytes(b"png")
    (tmp_path / "readme.md").write_text("readme", encoding="utf-8")

    project = ProjectData(
        base_directory=str(tmp_path),
        filter_enabled=True,
        filter_blacklist=False,
        filter_folders=["assets"],
    )
    step = Step1Files(project)
    found, _ = _scan(str(tmp_path))
    entries = _build_manifest(step, found)

    assert sorted(e["path"].replace("\\", "/") for e in entries) == [
        "src/assets/logo.png",
    ]

    # A new file inside a whitelisted folder must still be reported.
    (assets / "unexpected.dll").write_bytes(b"new")
    report = _verify(entries, str(tmp_path), FileRules.from_project(project))

    assert report["extra"] == ["src/assets/unexpected.dll"]
    assert report["passed"] == 1
    step.deleteLater()
