from builder.ui.step1_files import Step1Files
from builder.ui.workers.scan_worker import ScanWorker
from shared.project import ProjectData


def test_scan_worker_emits_batches_before_completing(qapp, tmp_path):
    for index in range(ScanWorker.BATCH_SIZE + 44):
        (tmp_path / f"file-{index:05d}.bin").write_bytes(b"payload")

    batch_sizes = []
    progress = []
    completions = []
    worker = ScanWorker([str(tmp_path)])
    worker.files_found.connect(lambda entries: batch_sizes.append(len(entries)))
    worker.progress.connect(lambda completed, total: progress.append((completed, total)))
    worker.scan_complete.connect(
        lambda total, skipped: completions.append((total, skipped))
    )

    worker.run()

    assert batch_sizes[:-1] == [ScanWorker.BATCH_SIZE]
    assert batch_sizes[-1] == 44
    assert completions == [(ScanWorker.BATCH_SIZE + 44, 0)]
    assert progress == [(ScanWorker.BATCH_SIZE + 44, ScanWorker.BATCH_SIZE + 44)]


def test_scan_worker_cancelled_before_run_returns_empty(qapp, tmp_path):
    (tmp_path / "file.txt").write_bytes(b"payload")
    batches = []
    completions = []
    worker = ScanWorker([str(tmp_path)])
    worker.cancel()
    worker.files_found.connect(batches.append)
    worker.scan_complete.connect(
        lambda total, skipped: completions.append((total, skipped))
    )

    worker.run()

    assert batches == []
    assert completions == [(0, 0)]


def test_step1_shows_scanning_empty_state(qapp, tmp_path):
    project = ProjectData(base_directory=str(tmp_path))
    step = Step1Files(project)
    table = step._file_table

    table.set_scanning(True)

    assert table._scanning is True
    assert table._scan_timer.isActive()
    assert table.accessibleName() == "正在扫描文件列表"

    table.set_scanning(False)

    assert table._scanning is False
    assert not table._scan_timer.isActive()
    assert table.accessibleName() == "文件列表"
    step.deleteLater()
