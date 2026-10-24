import json
import os
import subprocess
import sys
from pathlib import Path


BINARY_NAME = "fit-rec.exe" if os.name == "nt" else "fit-rec"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fitrec_tool_path() -> Path:
    if os.environ.get("FIT_REC_TOOL"):
        return Path(os.environ["FIT_REC_TOOL"])
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "fitrec" / BINARY_NAME
    target = PROJECT_ROOT / "target"
    return target / "release" / BINARY_NAME


def build_fit_document(
    checklists: dict,
    active_checklist: str,
    algorithm: str,
    exclude_paths: list[str],
    exclude_rules: dict,
    base_directory: str = "",
    data_shards: int = 8,
    parity_shards: int = 4,
) -> dict:
    named = {
        str(name): [_relative_entry(entry, base_directory) for entry in entries]
        for name, entries in (checklists or {}).items()
    }
    if not named:
        named = {"default": []}
    active = active_checklist if active_checklist in named else next(iter(named))

    return {
        "format_version": 1,
        "algorithm": algorithm or "sha256",
        "active_checklist": active,
        "checklists": named,
        "exclude_paths": [str(path) for path in (exclude_paths or [])],
        "exclude_rules": dict(exclude_rules or {}),
        "metadata": {},
    }


def _relative_entry(entry: dict, base_directory: str) -> dict:
    relative_entry = dict(entry)
    path = str(relative_entry.get("path", ""))
    if os.path.isabs(path):
        if not base_directory:
            raise RuntimeError("恢复文件清单包含绝对路径，但项目缺少基目录")
        try:
            path = os.path.relpath(path, base_directory)
        except ValueError as error:
            raise RuntimeError(f"无法转换为恢复文件相对路径: {path}") from error
    path = path.replace("\\", "/")
    if not path or path.startswith("../"):
        raise RuntimeError(f"恢复文件路径必须在项目基目录内: {path}")
    relative_entry["path"] = path
    return relative_entry


def validate_fitrec_key_path(path: str) -> Path:
    if not path:
        raise RuntimeError("请先生成或选择 Ed25519 私钥")
    key_path = Path(path)
    if not key_path.is_file():
        raise RuntimeError(f"Ed25519 私钥不存在: {key_path}")
    return key_path


def run_fitrec_keygen(private_key_path: str, public_key_path: str) -> tuple[Path, Path]:
    private_path = Path(private_key_path)
    public_path = Path(public_key_path)
    if private_path == public_path:
        raise RuntimeError("私钥和公钥必须使用不同文件")
    if private_path.exists():
        raise RuntimeError(f"私钥已存在，不能覆盖: {private_path}")
    if public_path.exists():
        raise RuntimeError(f"公钥已存在，不能覆盖: {public_path}")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    process = _run_tool([
        "keygen",
        "--private", str(private_path),
        "--public", str(public_path),
    ])
    if process.returncode != 0:
        raise RuntimeError(process.stdout.strip() or process.stderr.strip() or "Ed25519 密钥生成失败")
    return private_path, public_path


def run_fitrec_generate(
    document: dict,
    output_path: str,
    private_key_path: str,
    data_shards: int = 8,
    parity_shards: int = 4,
) -> Path:
    output = Path(output_path)
    key_path = validate_fitrec_key_path(private_key_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    public_path = Path(str(output) + ".pub")

    document_path = output.with_name(output.name + ".input.json")
    document_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    try:
        process = _run_tool([
            "generate",
            "--input", str(document_path),
            "--output", str(output),
            "--private-key", str(key_path),
            "--public-key", str(public_path),
            "--data-shards", str(data_shards),
            "--parity-shards", str(parity_shards),
        ])
    finally:
        document_path.unlink(missing_ok=True)

    if process.returncode != 0:
        raise RuntimeError(process.stdout.strip() or process.stderr.strip() or "生成 .fitrec 失败")
    if not output.is_file() or not public_path.is_file():
        raise RuntimeError("fit-rec 未生成恢复文件或公钥")
    return output


def _run_tool(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    tool = fitrec_tool_path()
    if not tool.is_file():
        raise RuntimeError(f"未找到 fit-rec 工具: {tool}")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(
        [str(tool), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=creationflags,
    )
