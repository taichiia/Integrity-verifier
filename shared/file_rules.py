"""File filtering rules shared by the Builder and the packed Verifier.

The Builder lets the user hide files (logs, build folders, oversized files)
before hashing.  Those files stay inside the verified folder, so the packed
verifier has to know the same rules; otherwise every ignored file shows up as
an "extra" file even though nothing changed on disk.
"""

from dataclasses import dataclass

RULE_VERSION = 1


@dataclass(frozen=True)
class FileRules:
    enabled: bool = False
    blacklist: bool = True
    extensions: tuple[str, ...] = ()
    folders: tuple[str, ...] = ()
    min_size: int = 0
    max_size: int = 0
    rule_version: int = RULE_VERSION

    @classmethod
    def from_filter_data(cls, data: dict | None) -> "FileRules":
        """Build rules from FilterPanel.get_filter_data() style payloads.

        Sizes accept either ``min_size``/``max_size`` in bytes or
        ``min_size_kb``/``max_size_kb`` as used by the Builder UI.
        """
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            blacklist=bool(data.get("blacklist", True)),
            extensions=tuple(
                str(e).lower().lstrip(".")
                for e in (data.get("extensions") or [])
            ),
            folders=tuple(
                str(f).lower().strip()
                for f in (data.get("folders") or [])
                if str(f).strip()
            ),
            min_size=_size_from(data, "min_size", "min_size_kb"),
            max_size=_size_from(data, "max_size", "max_size_kb"),
        )

    @classmethod
    def from_project(cls, project) -> "FileRules":
        return cls.from_filter_data({
            "enabled": getattr(project, "filter_enabled", False),
            "blacklist": getattr(project, "filter_blacklist", True),
            "extensions": getattr(project, "filter_extensions", []) or [],
            "folders": getattr(project, "filter_folders", []) or [],
            "min_size_kb": getattr(project, "filter_min_size_kb", 0),
            "max_size_kb": getattr(project, "filter_max_size_kb", 0),
        })

    @classmethod
    def from_config(cls, payload) -> "FileRules":
        if isinstance(payload, FileRules):
            return payload
        if not payload:
            return cls()
        return cls(
            enabled=bool(payload.get("enabled", False)),
            blacklist=bool(payload.get("blacklist", True)),
            extensions=tuple(
                str(e).lower().lstrip(".")
                for e in (payload.get("extensions") or [])
            ),
            folders=tuple(
                str(f).lower().strip()
                for f in (payload.get("folders") or [])
                if str(f).strip()
            ),
            min_size=int(payload.get("min_size", 0) or 0),
            max_size=int(payload.get("max_size", 0) or 0),
            rule_version=int(payload.get("rule_version", RULE_VERSION) or RULE_VERSION),
        )

    def to_config(self) -> dict:
        return {
            "rule_version": self.rule_version,
            "enabled": self.enabled,
            "blacklist": self.blacklist,
            "extensions": list(self.extensions),
            "folders": list(self.folders),
            "min_size": self.min_size,
            "max_size": self.max_size,
        }

    def excludes(self, rel_path: str, size: int = 0) -> bool:
        """Return True when the file is deliberately ignored by the user."""
        if not self.enabled:
            return False

        if self.min_size > 0 and size < self.min_size:
            return True
        if self.max_size > 0 and size > self.max_size:
            return True

        normalized = rel_path.replace("\\", "/")
        if self.extensions:
            hit = _extension_of(normalized) in self.extensions
            if self.blacklist and hit:
                return True
            if not self.blacklist and not hit:
                return True

        if self.folders:
            parts = {
                part.lower()
                for part in normalized.split("/")
                if part
            }
            hit = bool(parts & set(self.folders))
            if self.blacklist and hit:
                return True
            if not self.blacklist and not hit:
                return True

        return False

    def excludes_directory(self, name: str) -> bool:
        """Blacklist pruning helper: skip a whole folder when it is ignored."""
        if not self.enabled or not self.blacklist or not self.folders:
            return False
        return name.lower() in set(self.folders)


def _extension_of(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    if dot <= 0:  # no dot, or a dotfile such as ".gitignore"
        return ""
    return name[dot + 1:].lower()


def _size_from(data: dict, bytes_key: str, kb_key: str) -> int:
    if bytes_key in data:
        return int(data.get(bytes_key) or 0)
    return int(data.get(kb_key) or 0) * 1024
