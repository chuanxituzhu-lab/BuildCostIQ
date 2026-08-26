"""Local project workspace persistence for the user-facing workbench.

This adapter stores project state outside Core. It keeps the workbench
resumable without making Core depend on a filesystem layout or a UI concern.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .deployment import DeploymentStorageAdapter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-.")
    return text or "local-project"


class LocalProjectWorkspace:
    """Persist one JSON state file per project in a local runtime directory."""

    def __init__(self, root: Path | str = "runtime/projects", storage_adapter: DeploymentStorageAdapter | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.storage_adapter = storage_adapter

    def _project_lock(self, project_id: str):
        if self.storage_adapter is None:
            return nullcontext()
        return self.storage_adapter.project_lock(project_id)

    def _path(self, project_id: str) -> Path:
        return self.root / f"{_safe_id(project_id)}.json"

    def create(self, project_id: str, name: str) -> dict[str, Any]:
        with self._project_lock(project_id):
            return self._create_unlocked(project_id, name)

    def _create_unlocked(self, project_id: str, name: str) -> dict[str, Any]:
        existing = self.load(project_id)
        if existing:
            existing["project"]["name"] = name or existing["project"]["name"]
            existing["project"]["updated_at"] = _now()
            return self._save_unlocked(existing)
        stamp = _now()
        state = {
                "project": {
                    "id": project_id,
                    "name": name or project_id,
                    "status": "active",
                    "created_at": stamp,
                    "updated_at": stamp,
                    "revision": 0,
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
                "events": [],
                "event_distillation": None,
                # Adapter-owned coordination and line-ingestion projections. They
                # reference Core/P01-P08 facts and never replace those facts.
                "line_adaptations": [],
                "collaboration": {"tasks": [], "decisions": []},
                "relationships": [],
                "golden_scenario": None,
                "basis_references": [],
                "alert_snapshots": [],
                # Role-owned work products are adapter projections.  They are
                # linked to Core/Event/Evidence but never replace those facts.
                "role_work_products": [],
                "audit_log": [],
            }
        return self._save_unlocked(state)

    def load(self, project_id: str) -> dict[str, Any] | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, state: Mapping[str, Any]) -> dict[str, Any]:
        project_id = str(state["project"]["id"])
        with self._project_lock(project_id):
            return self._save_unlocked(state)

    def _save_unlocked(self, state: Mapping[str, Any]) -> dict[str, Any]:
        project_id = str(state["project"]["id"])
        payload = dict(state)
        payload["project"] = dict(payload["project"])
        payload["project"]["updated_at"] = _now()
        payload["project"]["revision"] = int(payload["project"].get("revision", 0) or 0) + 1
        target = self._path(project_id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(target)
        return payload

    def set_stage(self, project_id: str, stage: str, result: Mapping[str, Any]) -> dict[str, Any]:
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            state[stage] = {"status": "completed", "updated_at": _now(), "result": dict(result)}
            return self._save_unlocked(state)

    def next_event_id(self, project_id: str) -> str:
        """Return the next human-readable permanent event id for a project."""
        state = self.load(project_id) or self.create(project_id, project_id)
        year = datetime.now(timezone.utc).year
        prefix = f"EV-{year}-"
        numbers = []
        for event in list(state.get("events") or []):
            value = str(event.get("event_id", ""))
            if value.startswith(prefix):
                try:
                    numbers.append(int(value.removeprefix(prefix)))
                except ValueError:
                    continue
        return f"{prefix}{(max(numbers, default=0) + 1):04d}"

    def save_event(self, project_id: str, event: Mapping[str, Any]) -> dict[str, Any]:
        """Persist an event without replacing its append-only history."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            events = [dict(item) for item in list(state.get("events") or [])]
            event_payload = dict(event)
            event_id = str(event_payload.get("event_id", "")).strip()
            if not event_id:
                raise ValueError("工程事件缺少永久编号")
            replaced = False
            for index, existing in enumerate(events):
                if str(existing.get("event_id", "")) == event_id:
                    previous_history = list((existing.get("governance") or {}).get("status_history") or [])
                    current_history = list((event_payload.get("governance") or {}).get("status_history") or [])
                    if len(current_history) < len(previous_history):
                        event_payload.setdefault("governance", {})["status_history"] = previous_history
                    events[index] = event_payload
                    replaced = True
                    break
            if not replaced:
                events.append(event_payload)
            state["events"] = events
            return self._save_unlocked(state)

    def set_event_distillation(self, project_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
        """Save the latest local/text/fused snapshot separately from events."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            snapshot = dict(result)
            snapshot["updated_at"] = _now()
            state["event_distillation"] = snapshot
            return self._save_unlocked(state)

    def record_alert_snapshot(
        self,
        project_id: str,
        result: Mapping[str, Any],
        source_id: str = "",
    ) -> dict[str, Any]:
        """Persist a local review snapshot for weekly/monthly issue trends."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
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
            return self._save_unlocked(state)

    def add_source(self, project_id: str, source: Mapping[str, Any]) -> dict[str, Any]:
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            sources = list(state.get("sources") or [])
            sources = [item for item in sources if item.get("source_id") != source.get("source_id")]
            sources.append(dict(source))
            state["sources"] = sources
            return self._save_unlocked(state)

    def add_basis_reference(self, project_id: str, basis: Mapping[str, Any], stage: str) -> dict[str, Any]:
        """Store a point-in-time basis snapshot selected by a project stage."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            references = [
                item for item in list(state.get("basis_references") or [])
                if not (item.get("basis_id") == basis.get("basis_id") and item.get("stage") == stage)
            ]
            snapshot = dict(basis)
            snapshot["stage"] = stage
            snapshot["referenced_at"] = _now()
            references.append(snapshot)
            state["basis_references"] = references
            return self._save_unlocked(state)

    def append_audit(
        self,
        project_id: str,
        action: str,
        actor: Mapping[str, Any] | str,
        target: str,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an immutable user-facing audit event to the project state."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
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
            return self._save_unlocked(state)

    def modify_source(
        self,
        project_id: str,
        source_id: str,
        changes: Mapping[str, Any],
        actor: Mapping[str, Any] | str,
    ) -> dict[str, Any]:
        """Change source metadata only; original content remains content-addressed."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
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
            return self._save_unlocked(state)

    def soft_delete_source(
        self,
        project_id: str,
        source_id: str,
        actor: Mapping[str, Any] | str,
    ) -> dict[str, Any]:
        """Hide a source from active work while retaining its bytes and audit trail."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
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
            return self._save_unlocked(state)

    def add_role_work_product(self, project_id: str, product: Mapping[str, Any]) -> dict[str, Any]:
        """Append one role-owned work product to the project projection."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                state = self._create_unlocked(project_id, project_id)
            product_id = str(product.get("product_id", "")).strip()
            if not product_id:
                raise ValueError("岗位成果缺少 product_id")
            products = [dict(item) for item in list(state.get("role_work_products") or [])]
            if any(str(item.get("product_id")) == product_id for item in products):
                raise ValueError("岗位成果编号已经存在")
            products.append(dict(product))
            state["role_work_products"] = products[-1000:]
            return self._save_unlocked(state)

    def update_role_work_product(self, project_id: str, product_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        """Append an auditable update to one role projection without replacing facts."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                raise FileNotFoundError("项目尚未建立")
            products = [dict(item) for item in list(state.get("role_work_products") or [])]
            target = next((item for item in products if str(item.get("product_id")) == str(product_id)), None)
            if target is None:
                raise FileNotFoundError("岗位成果不存在")
            for key, value in updates.items():
                if isinstance(value, Mapping) and isinstance(target.get(key), Mapping):
                    merged = dict(target.get(key) or {})
                    merged.update(dict(value))
                    target[key] = merged
                else:
                    target[key] = value
            state["role_work_products"] = products[-1000:]
            return self._save_unlocked(state)
