from builder.ui.main_window import BuilderMainWindow
from builder.ui.theme import generate_builder_stylesheet


def test_builder_theme_does_not_emit_unknown_box_shadow():
    assert "box-shadow" not in generate_builder_stylesheet().lower()


def test_tools_menu_external_test_wires_step3_flow(tmp_path, monkeypatch, qapp):
    from shared.checksum_file import write_csv

    cs_path = tmp_path / "hashes.csv"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    write_csv([("app.dll", "abc123")], str(cs_path), algorithm="sha512")

    from builder.ui.widgets.dialogs import ExternalTestDialog
    monkeypatch.setattr(ExternalTestDialog, "exec", lambda self: True)
    monkeypatch.setattr(
        ExternalTestDialog,
        "get_values",
        lambda self: {"checksum_path": str(cs_path), "target_dir": str(target_dir)},
    )

    win = BuilderMainWindow()
    captured = {}

    def fake_run_simulation():
        captured["target"] = win._step3._sim_path.text()
        captured["entries"] = win._project.checksum_entries
        captured["algorithm"] = win._project.checksum_algorithm

    win._step3._run_simulation = fake_run_simulation
    win._external_test()

    assert win._stack.currentIndex() == 2
    assert captured["target"] == str(target_dir)
    assert captured["entries"] == [{"path": "app.dll", "hash": "abc123", "status": "ok"}]
    assert captured["algorithm"] == "sha512"
