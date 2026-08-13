"""Local project workspace persistence for the user-facing workbench.

This adapter stores project state outside Core. It keeps the workbench
resumable without making Core depend on a filesystem layout or a UI concern.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-.")
    return text or "local-project"


class LocalProjectWorkspace:
    """Persist one JSON state file per project in a local runtime directory."""

    def __init__(self, root: Path | str = "runtime/projects") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self.root / f"{_safe_id(project_id)}.json"

    def create(self, project_id: str, name: str) -> dict[str, Any]:
        existing = self.load(project_id)
        if existing:
            existing["project"]["name"] = name or existing["project"]["name"]
            existing["project"]["updated_at"] = _now()
            self.save(existing)
            return existing
        stamp = _now()
        state = {
            "project": {
                "id": project_id,
                "name": name or project_id,
                "status": "active",
                "created_at": stamp,
                "updated_at": stamp,
            },
            "sources": [],
            "boq": None,
            "cost_plan": None,
            "review": None,
        }
        self.save(state)
        return state

    def load(self, project_id: str) -> dict[str, Any] | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, state: Mapping[str, Any]) -> dict[str, Any]:
        project_id = str(state["project"]["id"])
        payload = dict(state)
        payload["project"] = dict(payload["project"])
        payload["project"]["updated_at"] = _now()
        target = self._path(project_id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(target)
        return payload

    def set_stage(self, project_id: str, stage: str, result: Mapping[str, Any]) -> dict[str, Any]:
        state = self.load(project_id) or self.create(project_id, project_id)
        state[stage] = {"status": "completed", "updated_at": _now(), "result": dict(result)}
        return self.save(state)

    def add_source(self, project_id: str, source: Mapping[str, Any]) -> dict[str, Any]:
        state = self.load(project_id) or self.create(project_id, project_id)
        sources = list(state.get("sources") or [])
        sources = [item for item in sources if item.get("source_id") != source.get("source_id")]
        sources.append(dict(source))
        state["sources"] = sources
        return self.save(state)
