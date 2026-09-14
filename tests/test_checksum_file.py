import os
import tempfile

from shared.checksum_file import read_csv, read_sfv, write_csv, write_sfv


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
    assert loaded == [("file1.txt", "abc123")]
