from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    name: str
    content_hash: str
    media_type: str = "application/octet-stream"
    id: str = field(default_factory=lambda: str(uuid4()))
    received_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Evidence:
    project_id: str
    source_id: str
    kind: str
    payload: Mapping[str, object]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))

