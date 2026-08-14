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
from uuid import uuid4


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
            "contract": None,
            "boq": None,
            "drawings": None,
            "baseline": None,
            "cost_plan": None,
            "changes": None,
            "evidence": None,
            "review": None,
            "alert_snapshots": [],
            "audit_log": [],
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

    def record_alert_snapshot(
        self,
        project_id: str,
        result: Mapping[str, Any],
        source_id: str = "",
    ) -> dict[str, Any]:
        """Persist a local review snapshot for weekly/monthly issue trends."""
        state = self.load(project_id) or self.create(project_id, project_id)
        snapshots = list(state.get("alert_snapshots") or [])
        snapshots.append(
            {
                "captured_at": _now(),
                "source_id": source_id,
                "risk": dict(result.get("risk") or {}),
                "summary": dict(result.get("summary") or {}),
                "findings": [dict(item) for item in result.get("findings") or [] if isinstance(item, Mapping)],
            }
        )
        state["alert_snapshots"] = snapshots[-120:]
        return self.save(state)

    def add_source(self, project_id: str, source: Mapping[str, Any]) -> dict[str, Any]:
        state = self.load(project_id) or self.create(project_id, project_id)
        sources = list(state.get("sources") or [])
        sources = [item for item in sources if item.get("source_id") != source.get("source_id")]
        sources.append(dict(source))
        state["sources"] = sources
        return self.save(state)

    def append_audit(
        self,
        project_id: str,
        action: str,
        actor: Mapping[str, Any] | str,
        target: str,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an immutable user-facing audit event to the project state."""
        state = self.load(project_id) or self.create(project_id, project_id)
        actor_payload = dict(actor) if isinstance(actor, Mapping) else {"id": str(actor)}
        event = {
            "id": str(uuid4()),
            "timestamp": _now(),
            "action": action,
            "actor": actor_payload,
            "target": target,
            "details": dict(details or {}),
        }
        state["audit_log"] = [*(state.get("audit_log") or []), event]
        return self.save(state)

    def modify_source(
        self,
        project_id: str,
        source_id: str,
        changes: Mapping[str, Any],
        actor: Mapping[str, Any] | str,
    ) -> dict[str, Any]:
        """Change source metadata only; original content remains content-addressed."""
        state = self.load(project_id) or self.create(project_id, project_id)
        sources = list(state.get("sources") or [])
        source = next((item for item in sources if item.get("source_id") == source_id), None)
        if source is None:
            raise FileNotFoundError("project source does not exist")
        if source.get("status") == "deleted":
            raise ValueError("deleted source metadata cannot be modified")
        allowed = {"name", "kind", "description", "category"}
        clean_changes = {key: value for key, value in changes.items() if key in allowed and str(value).strip()}
        if not clean_changes:
            raise ValueError("no editable source metadata was supplied")
        before = {key: source.get(key) for key in clean_changes}
        source.update(clean_changes)
        source["metadata_revision"] = int(source.get("metadata_revision", 0)) + 1
        source["metadata_updated_at"] = _now()
        actor_payload = dict(actor) if isinstance(actor, Mapping) else {"id": str(actor)}
        event = {
            "id": str(uuid4()),
            "timestamp": _now(),
            "action": "source.modified",
            "actor": actor_payload,
            "target": source_id,
            "details": {"before": before, "after": {key: source.get(key) for key in clean_changes}},
        }
        state["sources"] = sources
        state["audit_log"] = [*(state.get("audit_log") or []), event]
        return self.save(state)

    def soft_delete_source(
        self,
        project_id: str,
        source_id: str,
        actor: Mapping[str, Any] | str,
    ) -> dict[str, Any]:
        """Hide a source from active work while retaining its bytes and audit trail."""
        state = self.load(project_id) or self.create(project_id, project_id)
        sources = list(state.get("sources") or [])
        source = next((item for item in sources if item.get("source_id") == source_id), None)
        if source is None:
            raise FileNotFoundError("project source does not exist")
        if source.get("status") == "deleted":
            return state
        actor_payload = dict(actor) if isinstance(actor, Mapping) else {"id": str(actor)}
        stamp = _now()
        source["status"] = "deleted"
        source["deleted_at"] = stamp
        source["deleted_by"] = actor_payload
        event = {
            "id": str(uuid4()),
            "timestamp": stamp,
            "action": "source.deleted",
            "actor": actor_payload,
            "target": source_id,
            "details": {"name": source.get("name"), "content_hash": source.get("content_hash"), "soft_delete": True},
        }
        state["sources"] = sources
        state["audit_log"] = [*(state.get("audit_log") or []), event]
        return self.save(state)
