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
        self.progress = FakeSignal()
        self.speed = FakeSignal()
        self.file_done = FakeSignal()
        self.finished = FakeSignal()
        self.error_occurred = FakeSignal()

    def start(self):
        pass


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
