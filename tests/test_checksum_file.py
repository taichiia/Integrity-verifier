import os
import tempfile

from shared.checksum_file import (
    load_checksum_entries,
    read_csv,
    read_sfv,
    write_csv,
    write_sfv,
)


def test_csv_roundtrip():
    entries = [("subdir/file1.txt", "abc123"), ("file2.txt", "def456")]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.csv")
        write_csv(entries, path, algorithm="sha256")
        algorithm, loaded = read_csv(path)
    assert algorithm == "sha256"
    assert loaded == entries


def test_sfv_roundtrip():
    entries = [("folder/file1.txt", "abc123")]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.sfv")
        write_sfv(entries, path)
        loaded = read_sfv(path)
    assert loaded == [("folder/file1.txt", "abc123")]


def test_sfv_keeps_duplicate_base_names_apart():
    entries = [
        ("a/config.json", "hash-a"),
        ("b/config.json", "hash-b"),
        ("config.json", "hash-root"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.sfv")
        write_sfv(entries, path)
        loaded = read_sfv(path)

    assert loaded == entries
    assert len({name for name, _ in loaded}) == 3


def test_sfv_reads_legacy_basename_entries():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.sfv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("; legacy\napp.dll abc123\n*bin.dat def456\n")

        loaded = read_sfv(path)

    assert loaded == [("app.dll", "abc123"), ("bin.dat", "def456")]


def test_load_checksum_entries_detects_csv_algorithm():
    entries = [("app.dll", "abc123")]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.csv")
        write_csv(entries, path, algorithm="sha512")

        loaded, algorithm = load_checksum_entries(path)

    assert algorithm == "sha512"
    assert loaded == [{"path": "app.dll", "hash": "abc123", "status": "ok"}]


def test_load_checksum_entries_csv_defaults_to_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("path,hash\napp.dll,abc123\n")

        loaded, algorithm = load_checksum_entries(path)

    assert algorithm == "sha256"
    assert loaded == [{"path": "app.dll", "hash": "abc123", "status": "ok"}]


def test_load_checksum_entries_sfv_uses_fallback_algorithm():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hashes.sfv")
        write_sfv([("app.dll", "abc123")], path)

        loaded, algorithm = load_checksum_entries(path, fallback_algorithm="md5")

    assert algorithm == "md5"
    assert loaded == [{"path": "app.dll", "hash": "abc123", "status": "ok"}]
