import os
import tempfile

from shared.project import ProjectData, load_project, save_project


def test_save_and_load_roundtrip():
    data = ProjectData(base_directory="C:/tmp", file_paths=["a.txt"], project_name="Test")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "proj.fvp")
        save_project(data, path)
        loaded = load_project(path)
    assert loaded.base_directory == "C:/tmp"
    assert loaded.file_paths == ["a.txt"]
    assert loaded.project_name == "Test"


def test_save_excludes_password():
    data = ProjectData(encryption_password="should-not-be-saved")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "proj.fvp")
        save_project(data, path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    assert "should-not-be-saved" not in content
    assert "encryption_password" not in content


def test_load_ignores_unknown_fields():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "proj.fvp")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"base_directory": "x", "future_field": true}')
        loaded = load_project(path)
    assert loaded.base_directory == "x"


def test_load_populates_project_file_path():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "proj.fvp")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
        loaded = load_project(path)
    assert loaded.project_file_path == path
