from __future__ import annotations

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

