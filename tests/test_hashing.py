import os
import tempfile

import pytest

from shared.hashing import (
    SMALL_FILE_LIMIT,
    default_workers,
    hash_batch,
    hash_file,
    hash_generator,
)


def test_hash_file_sha256():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test data")
        path = f.name
    try:
        digest = hash_file(path, "sha256")
        assert digest == "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
    finally:
        os.unlink(path)


def test_hash_file_md5():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test data")
        path = f.name
    try:
        digest = hash_file(path, "md5")
        assert digest == "eb733a00c0c9d336e65691a37ab54293"
    finally:
        os.unlink(path)


def test_hash_file_missing_raises():
    with pytest.raises(FileNotFoundError):
        hash_file("no_such_file_xyz.bin")


def test_hash_file_large_file_path():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"mmap data")
        path = f.name
    try:
        digest = hash_file(path, "sha256")
        import hashlib
        expected = hashlib.sha256(b"mmap data").hexdigest()
        assert digest == expected
    finally:
        os.unlink(path)


def test_hash_file_crosses_small_file_boundary():
    payload = b"x" * (SMALL_FILE_LIMIT + 123)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(payload)
        path = f.name
    try:
        digest = hash_file(path, "sha256")
        import hashlib
        assert digest == hashlib.sha256(payload).hexdigest()
    finally:
        os.unlink(path)


def test_default_hash_workers_are_bounded():
    assert 1 <= default_workers() <= 4


def test_hash_batch_preserves_order():
    paths = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(f"data{i}".encode())
            paths.append(f.name)
    try:
        results = hash_batch(paths)
        assert [r[0] for r in results] == paths
        assert all(r[2] is None for r in results)
    finally:
        for p in paths:
            os.unlink(p)


def test_hash_batch_reports_errors():
    results = hash_batch(["no_such_file_xyz.bin"])
    assert results[0][1] == ""
    assert "not found" in results[0][2].lower()


def test_hash_batch_progress_callback():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"data")
        path = f.name
    try:
        calls = []
        hash_batch([path], progress_callback=lambda done, total, p: calls.append((done, total, p)))
        assert calls == [(1, 1, path)]
    finally:
        os.unlink(path)


def test_hash_generator_yields_results():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"data")
        path = f.name
    try:
        results = list(hash_generator([path]))
        assert len(results) == 1
        assert results[0][0] == path
        assert results[0][2] is None
    finally:
        os.unlink(path)
