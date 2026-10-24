import csv
import io


def write_csv(
    entries: list[tuple[str, str]],
    filepath: str,
    algorithm: str = "sha256",
) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(f"# Algorithm: {algorithm}\n")
        f.write(f"# Generated: {_timestamp()}\n")
        writer = csv.writer(f)
        writer.writerow(["path", "hash"])
        for rel_path, digest in entries:
            writer.writerow([rel_path, digest])


def read_csv(filepath: str) -> tuple[str, list[tuple[str, str]]]:
    algorithm = "sha256"
    entries = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    reader = csv.reader(io.StringIO("".join(
        line for line in lines if not line.startswith("#")
    )))
    for row in reader:
        if row and row[0] == "path":
            continue
        if len(row) >= 2:
            entries.append((row[0], row[1]))

    for line in lines:
        if line.startswith("# Algorithm:"):
            algorithm = line.split(":", 1)[1].strip()

    return algorithm, entries


def write_sfv(
    entries: list[tuple[str, str]],
    filepath: str,
) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"; Generated: {_timestamp()}\n")
        for rel_path, digest in entries:
            # Keep the relative path: two files with the same base name (for
            # example nested config.json files) must stay distinguishable.
            name = rel_path.replace("\\", "/")
            if name.startswith("./"):
                name = name[2:]
            name = name.lstrip("/")
            f.write(f"{name} {digest}\n")


def read_sfv(filepath: str) -> list[tuple[str, str]]:
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                name = parts[0]
                # Some SFV writers prefix binary-mode names with "*".
                if name.startswith("*"):
                    name = name[1:]
                entries.append((name, parts[1]))
    return entries


def load_checksum_entries(
    filepath: str,
    fallback_algorithm: str = "sha256",
) -> tuple[list[dict[str, str]], str]:
    """Load a checksum file and return normalized entries with its algorithm."""
    if filepath.lower().endswith(".csv"):
        algorithm, pairs = read_csv(filepath)
        return [
            {"path": rel_path, "hash": digest, "status": "ok"}
            for rel_path, digest in pairs
        ], algorithm

    pairs = read_sfv(filepath)
    return [
        {"path": rel_path, "hash": digest, "status": "ok"}
        for rel_path, digest in pairs
    ], fallback_algorithm


def _timestamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

