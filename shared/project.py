import json
import os
from dataclasses import dataclass, field


@dataclass
class ProjectData:
    base_directory: str = ""
    file_paths: list[str] = field(default_factory=list)
    filter_extensions: list[str] = field(default_factory=list)
    filter_folders: list[str] = field(default_factory=list)
    filter_blacklist: bool = True
    filter_min_size_kb: int = 0
    filter_max_size_kb: int = 0
    filter_enabled: bool = True

    checksum_algorithm: str = "sha256"
    checksum_output_path: str = ""
    checksum_format: str = "csv"
    checksum_entries: list[dict] = field(default_factory=list)

    private_key_path: str = ""
    encryption_password: str = ""
    enable_signing: bool = False
    enable_encryption: bool = False
    signature_algorithm: str = "RSA"

    verifier_title: str = "File Integrity Verifier"
    verifier_icon_path: str = ""
    verifier_version: str = "1.0.0.0"
    verifier_company: str = ""
    verifier_copyright: str = ""
    verifier_path_rule: str = "current_dir"
    verifier_subfolder: str = ""
    verifier_custom_template: str = ""
    verifier_embed_encrypted: bool = True
    verifier_enable_signature_verify: bool = True
    verifier_enable_antidebug: bool = False
    verifier_enable_antisanbox: bool = False
    verifier_active_checklist: str = "default"
    verifier_checklists: dict = field(default_factory=dict)

    project_name: str = "Untitled"
    project_file_path: str = ""


def save_project(data: ProjectData, filepath: str) -> None:
    d = _to_dict(data)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, default=str)
    data.project_file_path = filepath


def load_project(filepath: str) -> ProjectData:
    with open(filepath, "r", encoding="utf-8") as f:
        d = json.load(f)
    return _from_dict(d, filepath)


def _to_dict(data: ProjectData) -> dict:
    result = {}
    for field_name in data.__dataclass_fields__:
        value = getattr(data, field_name)
        if field_name == "encryption_password":
            continue
        result[field_name] = value
    return result


def _from_dict(d: dict, filepath: str) -> ProjectData:
    d.pop("encryption_password", None)
    known = set(ProjectData.__dataclass_fields__.keys())
    filtered = {k: v for k, v in d.items() if k in known}
    data = ProjectData(**filtered)
    data.project_file_path = filepath
    return data

