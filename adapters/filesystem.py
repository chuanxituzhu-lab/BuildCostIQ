from __future__ import annotations

import re
from pathlib import Path

from core.models import SourceDocument
from core.provenance import sha256_bytes


class ImmutableSourceStore:
    """Content-addressed source store; an existing hash is never overwritten."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def ingest(self, name: str, content: bytes, media_type: str = "application/octet-stream") -> SourceDocument:
        digest = sha256_bytes(content)
        target = self.root / digest
        if not target.exists():
            target.write_bytes(content)
            target.chmod(0o444)
        return SourceDocument(name=name, content_hash=digest, media_type=media_type)

    def path_for(self, source: SourceDocument | str) -> Path:
        """Return the absolute local path for a stored source without reading it."""
        content_hash = source.content_hash if isinstance(source, SourceDocument) else str(source)
        return (self.root / content_hash).resolve()

    def read(self, source: SourceDocument) -> bytes:
        content = (self.root / source.content_hash).read_bytes()
        if sha256_bytes(content) != source.content_hash:
            raise ValueError("Source integrity check failed")
        return content


class CategorizedArchiveStore:
    """Materialize read-only copies under a human-readable local folder tree.

    The immutable source store remains the integrity authority. This adapter
    only adds a navigable copy for local project work and never overwrites an
    existing file with different content.
    """

    _RESERVED_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _safe_segment(cls, value: str, fallback: str = "未分类") -> str:
        text = str(value or "").strip().strip("/\\")
        text = re.sub(r'[<>:"/\\|?*]', "_", text).rstrip(" .")
        if not text or text in {".", ".."}:
            return fallback
        if text.upper() in cls._RESERVED_NAMES:
            return f"_{text}"
        return text

    @classmethod
    def _segments(cls, value: str) -> list[str]:
        return [
            cls._safe_segment(part)
            for part in re.split(r"[/\\]+", str(value or ""))
            if part.strip("/\\ ")
        ]

    def materialize(
        self,
        scope: str,
        archive_area: str,
        archive_category: str,
        filename: str,
        source_path: Path,
        content_hash: str,
    ) -> Path:
        """Copy one immutable source into its project/category folder."""
        area_parts = self._segments(archive_area)
        category = self._safe_segment(archive_category, fallback="") if archive_category else ""
        if category and (not area_parts or area_parts[-1] != category):
            area_parts.append(category)
        safe_name = self._safe_segment(Path(filename).name, fallback="source.bin")
        target_dir = self.root / self._safe_segment(scope, fallback="shared")
        for part in area_parts:
            target_dir /= part
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / safe_name
        if target.exists():
            try:
                if sha256_bytes(target.read_bytes()) == content_hash:
                    return target.resolve()
            except OSError:
                pass
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix
            target = target_dir / f"{stem}~{content_hash[:12]}{suffix}"
            if target.exists() and sha256_bytes(target.read_bytes()) == content_hash:
                return target.resolve()
        temporary = target.with_name(f".{target.name}.{content_hash[:12]}.tmp")
        temporary.write_bytes(source_path.read_bytes())
        temporary.replace(target)
        target.chmod(0o444)
        return target.resolve()

