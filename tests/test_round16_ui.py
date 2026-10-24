from builder.ui.step1_files import Step1Files
from builder.ui.widgets.file_table import FileTableModel, dedupe_key
from builder.ui.widgets.progress_panel import ProgressPanel, _format_duration
from shared.project import ProjectData


def test_file_model_reuses_precomputed_dedupe_keys(qapp):
    model = FileTableModel()

    assert dedupe_key({"path": "first.txt", "_identity_key": "IDENTITY"}) == "IDENTITY"
    assert model.add_files([
        {"path": "first.txt", "_identity_key": "IDENTITY", "size": 1},
    ]) == 1
    assert dedupe_key(model.get_all()[0]) == "IDENTITY"
    assert model.add_files([
        {"path": "FIRST.TXT", "_identity_key": "IDENTITY", "size": 2},
    ]) == 0
    assert model.rowCount() == 1
    assert model.get_all()[0]["size"] == 1


def test_step1_keeps_scan_identity_keys(qapp, tmp_path):
    project = ProjectData(base_directory=str(tmp_path))
    step = Step1Files(project)

    step._on_files_found([
        (str(tmp_path / "A.txt"), 3, 100.0),
        (str(tmp_path / "a.txt"), 4, 101.0),
    ])

    entries = step._file_table.model().get_all()
    assert len(entries) == 1
    assert entries[0]["_identity_key"]
    assert step._known_paths == {entries[0]["_identity_key"]}
    step.deleteLater()


def test_progress_panel_shows_remaining_time(qapp):
    panel = ProgressPanel()

    panel.set_progress(500, 2000)
    panel.set_speed(10.0)

    assert panel._speed_label.text() == "速度: 10.0 文件/秒 · 剩余约 2 分 30 秒"

    panel.set_progress(2000, 2000)
    panel.set_speed(10.0)

    assert panel._speed_label.text() == "速度: 10.0 文件/秒 · 已完成"


def test_progress_duration_formats():
    assert _format_duration(59.4) == "59 秒"
    assert _format_duration(60) == "1 分 00 秒"
    assert _format_duration(3600) == "1 小时 00 分"
    assert _format_duration(86400) == "1 天 00 小时"
