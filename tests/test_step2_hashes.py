import builder.ui.step2_hashes as step2_hashes
from shared.project import ProjectData
from builder.ui.step2_hashes import Step2Hashes


class FakeSignal:
    def __init__(self):
        self.connected = None

    def connect(self, callback):
        self.connected = callback

    def emit(self, *args):
        if self.connected:
            self.connected(*args)


class FakeHashWorker:
    def __init__(self, paths, algorithm="sha256", **kwargs):
        self.paths = paths
        self.algorithm = algorithm
        self.cancel_requested = False
        self.progress = FakeSignal()
        self.speed = FakeSignal()
        self.file_done = FakeSignal()
        self.files_done = FakeSignal()
        self.completed = FakeSignal()
        self.finished = FakeSignal()
        self.error_occurred = FakeSignal()

    def start(self):
        pass

    def cancel(self):
        self.cancel_requested = True


def test_hash_manifest_updates_on_file_done(qapp, tmp_path):
    project = ProjectData()
    project.base_directory = str(tmp_path)
    project.checksum_entries = [{
        "path": "a.txt", "hash": "", "status": "pending",
    }]
    step = Step2Hashes(project)

    step._on_file_done(str(tmp_path / "a.txt"), "abc", "")

    assert step._checksum_entries[0]["status"] == "ok"
    assert "[ OK ] abc  a.txt" in step._manifest.toPlainText()


def test_start_hash_shows_pending_manifest(qapp, tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("payload", encoding="utf-8")
    project = ProjectData()
    project.base_directory = str(tmp_path)
    project.checksum_entries = [
        {"path": "a.txt", "hash": "", "status": "pending"},
        {"path": "missing.txt", "hash": "", "status": "pending"},
    ]
    step = Step2Hashes(project)
    monkeypatch.setattr(step2_hashes, "HashWorker", FakeHashWorker)

    step._start_hash()

    assert step._checksum_entries[0]["status"] == "pending"
    assert step._checksum_entries[1]["status"] == "error"
    assert "PEND" in step._manifest.toPlainText()
    assert "ERR" in step._manifest.toPlainText()


def test_stop_hash_marks_cancelled_result(qapp, tmp_path, monkeypatch):
    output = tmp_path / "checksums.csv"
    (tmp_path / "a.txt").write_text("payload", encoding="utf-8")
    project = ProjectData()
    project.base_directory = str(tmp_path)
    project.checksum_entries = [
        {"path": "a.txt", "hash": "", "status": "pending"},
    ]
    step = Step2Hashes(project)
    step._out_path.setText(str(output))
    monkeypatch.setattr(step2_hashes, "HashWorker", FakeHashWorker)

    step._start_hash()
    worker = step._worker
    step._stop_hash()

    assert worker.cancel_requested is True
    assert step._cancel_requested is True
    assert step._stop_btn.isEnabled() is False
    assert step._pause_btn.isEnabled() is False

    step._on_files_done([("a.txt", "abc", "")])
    step._on_finished([("a.txt", "abc", "")])
    step._on_worker_finished()

    assert "已停止: 1 文件已哈希" in step._progress_panel._log.toPlainText()
    assert step._stop_btn.isEnabled() is False
    assert step._start_btn.isEnabled() is True
    assert output.exists() is False


def test_manifest_result_updates_are_indexed(qapp, tmp_path):
    project = ProjectData()
    project.base_directory = str(tmp_path)
    project.checksum_entries = [
        {"path": f"file-{i}.txt", "hash": "", "status": "pending"}
        for i in range(100)
    ]
    step = Step2Hashes(project)

    step.refresh_from_project()
    step._update_manifest()
    assert step._entry_rows[step._normalized_path("file-40.txt")] == 40

    step._set_entry_result(str(tmp_path / "file-40.txt"), "digest-40", "ok")

    assert step._checksum_entries[40]["hash"] == "digest-40"
    assert step._checksum_entries[40]["status"] == "ok"
    assert step._manifest.toPlainText().count("digest-40") == 1
    assert step._manifest.toPlainText().splitlines()[40] == "[ OK ] digest-40  file-40.txt"
