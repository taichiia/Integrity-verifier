import hashlib
import mmap
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterator

ONE_GB = 1_073_741_824
READ_CHUNK = 65536


def hash_file(filepath: str, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    size = os.path.getsize(filepath)

    if size > ONE_GB:
        with open(filepath, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                for offset in range(0, size, READ_CHUNK):
                    h.update(m[offset:offset + READ_CHUNK])
    else:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(READ_CHUNK)
                if not chunk:
                    break
                h.update(chunk)

    return h.hexdigest()


def hash_batch(
    paths: list[str],
    algorithm: str = "sha256",
    max_workers: int | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[tuple[str, str, str | None]]:
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 4) - 1)

    total = len(paths)
    results: dict[str, tuple[str, str | None]] = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_hash_single, p, algorithm): p
            for p in paths
        }

        for future in as_completed(future_map):
            path = future_map[future]
            try:
                digest, error = future.result()
            except Exception as exc:
                digest, error = "", str(exc)
            results[path] = (digest, error)
            completed += 1
            if progress_callback:
                progress_callback(completed, total, path)

    return [(p, results[p][0], results[p][1]) for p in paths]


def hash_generator(
    paths: list[str],
    algorithm: str = "sha256",
    max_workers: int | None = None,
) -> Iterator[tuple[str, str, str | None]]:
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 4) - 1)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_hash_single, p, algorithm): p
            for p in paths
        }

        for future in as_completed(future_map):
            path = future_map[future]
            try:
                digest, error = future.result()
            except Exception as exc:
                digest, error = "", str(exc)
            yield path, digest, error


def _hash_single(filepath: str, algorithm: str) -> tuple[str, str | None]:
    try:
        return hash_file(filepath, algorithm), None
    except PermissionError:
        return "", "Permission denied"
    except FileNotFoundError:
        return "", "File not found"
    except OSError as e:
        return "", str(e)
    except Exception as e:
        return "", f"Unexpected: {e}"

