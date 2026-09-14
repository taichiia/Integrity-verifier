from shared.preferences import create_settings
from shared.theme import set_theme_mode
from verifier.ui.main_window import VerifierMainWindow


def test_results_sort_by_manifest_order_and_keep_extras_last(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)

    win = VerifierMainWindow({}, settings=settings)
    win._manifest_order = ["b.txt", "a.txt", "c.txt"]
    win._all_results = [
        {"path": "extra.txt", "status": "extra", "expected": "", "actual": ""},
        {"path": "c.txt", "status": "missing", "expected": "abc", "actual": ""},
        {"path": "a.txt", "status": "fail", "expected": "abc", "actual": "xyz"},
        {"path": "b.txt", "status": "pass", "expected": "abc", "actual": "abc"},
    ]

    win._sort_results_for_display()

    assert [entry["path"] for entry in win._all_results] == [
        "b.txt", "a.txt", "c.txt", "extra.txt",
    ]
    win.close()
    set_theme_mode("light")


def test_verify_done_sorts_results_after_completion_order(tmp_path, qapp, monkeypatch):
    settings = create_settings(tmp_path / "settings.ini")
    monkeypatch.setattr(VerifierMainWindow, "_start_verification", lambda self: None)

    win = VerifierMainWindow({}, settings=settings)
    target = tmp_path / "target"
    target.mkdir()
    win._target_path.setText(str(target))
    win._manifest_order = ["b.txt", "a.txt"]
    win._verify_total = 2
    win._verify_started_at = 0.0

    expected_map = {
        str(target / "a.txt"): "abc",
        str(target / "b.txt"): "abc",
    }
    win._on_verify_file(str(target / "a.txt"), "wrong", "", expected_map, str(target))
    win._on_verify_file(str(target / "b.txt"), "abc", "", expected_map, str(target))
    win._on_verify_done()

    assert [entry["path"] for entry in win._all_results] == ["b.txt", "a.txt"]
    assert [entry["path"] for entry in win._result_model._results] == [
        "b.txt", "a.txt",
    ]
    win.close()
    set_theme_mode("light")
