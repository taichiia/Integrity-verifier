from PySide6.QtCore import Qt

from builder.ui.step2_hashes import Step2Hashes
from builder.ui.widgets.file_table import FileTableModel
from builder.ui.workers.hash_worker import HashWorker
from shared.project import ProjectData


def test_hash_worker_batches_file_results(qapp, tmp_path):
    paths = []
    for index in range(HashWorker.BATCH_SIZE + 44):
        path = tmp_path / f"file-{index:04d}.txt"
        path.write_bytes(f"payload-{index}".encode("utf-8"))
        paths.append(str(path))

    batches: list[list[tuple[str, str, str]]] = []
    completed: list[tuple[str, str, str]] = []
    worker = HashWorker(paths, algorithm="sha256", max_workers=2)
    worker.files_done.connect(batches.append)
    worker.completed.connect(completed.extend)

    worker.run()

    assert len(completed) == len(paths)
    assert all(len(batch) <= HashWorker.BATCH_SIZE for batch in batches)
    assert len(batches) < len(paths)


def test_step2_applies_batched_hash_results(qapp, tmp_path):
    paths = [tmp_path / f"file-{index}.txt" for index in range(3)]
    for index, path in enumerate(paths):
        path.write_text(f"payload-{index}", encoding="utf-8")

    project = ProjectData(base_directory=str(tmp_path))
    project.checksum_entries = [
        {"path": path.name, "hash": "", "status": "pending"}
        for path in paths
    ]
    step = Step2Hashes(project)
    step.refresh_from_project()
    step._is_running = True

    step._on_files_done([
        (str(paths[0]), "digest-0", ""),
        (str(paths[1]), "digest-1", ""),
        (str(paths[2]), "", "File not found"),
    ])

    assert step._checksum_entries[0]["hash"] == "digest-0"
    assert step._checksum_entries[1]["hash"] == "digest-1"
    assert step._checksum_entries[2]["status"] == "error"
    assert step._pending_manifest_rows == {0, 1, 2}

    step._flush_manifest_updates()
    assert step._manifest.toPlainText().count("digest-") == 2
    assert step._manifest.toPlainText().count("ERR") == 1


def test_step2_throttles_progress_widget_updates(qapp, tmp_path):
    project = ProjectData(base_directory=str(tmp_path))
    step = Step2Hashes(project)

    step._on_progress(1, 2, str(tmp_path / "a.txt"))
    step._on_speed(3.0)

    assert step._pending_progress == (1, 2, str(tmp_path / "a.txt"))
    assert step._pending_speed == 3.0
    assert step._progress_panel._current_label.text() == "等待中..."

    step._flush_progress_updates()

    assert step._progress_panel._current_label.text() == str(tmp_path / "a.txt")
    assert step._progress_panel._speed_label.text().startswith("速度: 3.0")
    assert step._pending_progress is None
    assert step._pending_speed is None


def test_file_model_removes_selected_rows_in_batches(qapp):
    entries = [
        {"path": f"file-{index}.txt", "size": index, "mtime": 0, "checked": True}
        for index in range(6)
    ]
    model = FileTableModel()
    model.set_files(entries)

    model.remove_rows([0, 1, 3, 5])

    assert [entry["path"] for entry in model.get_all()] == [
        "file-2.txt",
        "file-4.txt",
    ]
    assert model.checked_count() == 2


def test_file_model_bulk_selection_emits_check_state_changes(qapp):
    entries = [
        {"path": f"file-{index}.txt", "size": index, "mtime": 0, "checked": False}
        for index in range(4)
    ]
    model = FileTableModel()
    model.set_files(entries)
    changes = []
    model.dataChanged.connect(
        lambda first, last, roles: changes.append(
            (first.row(), last.row(), roles)
        )
    )

    model.select_all()
    model.invert_selection()

    assert model.checked_count() == 0
    assert changes == [
        (0, 3, [Qt.ItemDataRole.CheckStateRole]),
        (0, 3, [Qt.ItemDataRole.CheckStateRole]),
    ]
