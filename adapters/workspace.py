"""Local project workspace persistence for the user-facing workbench.

This adapter stores project state outside Core. It keeps the workbench
resumable without making Core depend on a filesystem layout or a UI concern.
"""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from core.execution_ledger import (
    GENESIS_HASH,
    ExecutionLedgerError,
    create_execution_event,
    derive_agent_ops_plan_states,
    idempotency_fingerprint,
    validate_execution_transition,
    verify_execution_chain,
)

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
                "execution_ledger": [],
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

    def append_execution_event(self, project_id: str, event_fields: Mapping[str, Any]) -> dict[str, Any]:
        """Append one hash-linked S06 execution event to the existing project file.

        This is a passive evidence/status record. It does not authorize an
        action, run a module, approve a result, or promote a Canonical fact.
        """
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                raise FileNotFoundError("项目尚未建立，不能写入运行记录")
            if str((state.get("project") or {}).get("id", "")) != project_id:
                raise ExecutionLedgerError("项目存储路径与项目编号不一致")
            ledger = [dict(item) for item in list(state.get("execution_ledger") or [])]
            previous_hash = verify_execution_chain(ledger, project_id=project_id)
            fields = dict(event_fields)
            supplied_project_id = fields.pop("project_id", project_id)
            if supplied_project_id != project_id:
                raise ExecutionLedgerError("运行记录项目范围与当前工作区不一致")
            allowed_fields = {
                "run_id",
                "workflow_id",
                "module_id",
                "event_type",
                "actor_type",
                "actor_id",
                "target_type",
                "target_id",
                "payload_summary",
                "evidence_refs",
                "result_version_refs",
                "checkpoint_ref",
                "idempotency_key",
                "data_classification",
                "agent_ops_state",
            }
            unexpected_fields = set(fields) - allowed_fields
            if unexpected_fields:
                raise ExecutionLedgerError(f"运行记录包含未授权字段：{', '.join(sorted(unexpected_fields))}")
            event = create_execution_event(
                **fields,
                project_id=project_id,
                previous_event_hash=previous_hash or GENESIS_HASH,
            )
            for existing in ledger:
                if existing.get("run_id") == event["run_id"] and existing.get("idempotency_key") == event["idempotency_key"]:
                    if idempotency_fingerprint(existing) == idempotency_fingerprint(event):
                        return existing
                    raise ExecutionLedgerError("相同幂等键对应了不同运行事件，已拒绝重试")
            self._validate_execution_references(state, ledger, event)
            validate_execution_transition(ledger, event)
            ledger.append(event)
            state["execution_ledger"] = ledger
            audit_actor = {"id": event["actor_id"], "type": event["actor_type"]}
            audit_record = {
                "id": str(uuid4()),
                "timestamp": event["occurred_at"],
                "action": "execution_ledger.appended",
                "actor": audit_actor,
                "target": event["run_id"],
                "details": {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "event_hash": event["event_hash"],
                },
            }
            state["audit_log"] = [*(state.get("audit_log") or []), audit_record]
            self._save_unlocked(state)
            return event

    def append_workflow_batch(
        self,
        project_id: str,
        event_fields: list[Mapping[str, Any]],
        record_blobs: Mapping[str, Mapping[str, Any]],
        *,
        expected_last_event_hash: str,
    ) -> list[dict[str, Any]]:
        """Atomically append workflow evidence and its content-addressed records.

        The caller supplies the last hash it reviewed. A competing write makes
        the action stale instead of allowing two approvals against one state.
        """
        if not event_fields:
            raise ExecutionLedgerError("工作流操作没有可记录事件")
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                raise FileNotFoundError("项目尚未建立，不能写入工作流记录")
            if str((state.get("project") or {}).get("id", "")) != project_id:
                raise ExecutionLedgerError("项目存储路径与项目编号不一致")
            ledger = [dict(item) for item in list(state.get("execution_ledger") or [])]
            previous_hash = verify_execution_chain(ledger, project_id=project_id)
            if str(expected_last_event_hash or GENESIS_HASH) != str(previous_hash or GENESIS_HASH):
                raise ExecutionLedgerError("流程状态已被其他人员更新，请刷新后重新操作")

            stored_blobs = dict(state.get("business_workflow_blobs") or {})
            clean_blobs: dict[str, dict[str, Any]] = {}
            for digest, value in record_blobs.items():
                blob = dict(value)
                packed = json.dumps(blob, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                actual = hashlib.sha256(packed).hexdigest()
                if actual != str(digest):
                    raise ExecutionLedgerError("工作流成果内容哈希不匹配")
                existing = stored_blobs.get(digest)
                if existing is not None and existing != blob:
                    raise ExecutionLedgerError("内容寻址工作流成果出现哈希冲突")
                clean_blobs[str(digest)] = blob

            allowed_fields = {
                "run_id", "workflow_id", "module_id", "event_type", "actor_type", "actor_id",
                "target_type", "target_id", "payload_summary", "evidence_refs", "result_version_refs",
                "checkpoint_ref", "idempotency_key", "data_classification", "agent_ops_state",
            }
            appended: list[dict[str, Any]] = []
            for supplied in event_fields:
                fields = dict(supplied)
                supplied_project_id = fields.pop("project_id", project_id)
                if supplied_project_id != project_id:
                    raise ExecutionLedgerError("工作流事件项目范围与当前工作区不一致")
                unexpected_fields = set(fields) - allowed_fields
                if unexpected_fields:
                    raise ExecutionLedgerError(f"工作流事件包含未授权字段：{', '.join(sorted(unexpected_fields))}")
                event = create_execution_event(
                    **fields,
                    project_id=project_id,
                    previous_event_hash=previous_hash or GENESIS_HASH,
                )
                for existing_event in ledger:
                    if existing_event.get("run_id") == event["run_id"] and existing_event.get("idempotency_key") == event["idempotency_key"]:
                        if idempotency_fingerprint(existing_event) == idempotency_fingerprint(event):
                            raise ExecutionLedgerError("该操作已登记，请刷新查看最新流程状态")
                        raise ExecutionLedgerError("相同幂等键对应了不同工作流事件，已拒绝重试")
                self._validate_execution_references(state, ledger, event)
                validate_execution_transition(ledger, event)
                ledger.append(event)
                appended.append(event)
                previous_hash = event["event_hash"]

            state["execution_ledger"] = ledger
            stored_blobs.update(clean_blobs)
            state["business_workflow_blobs"] = stored_blobs
            for event in appended:
                state["audit_log"] = [*(state.get("audit_log") or []), {
                    "id": str(uuid4()), "timestamp": event["occurred_at"],
                    "action": "business_workflow.event_recorded",
                    "actor": {"id": event["actor_id"], "type": event["actor_type"]},
                    "target": event["run_id"],
                    "details": {"event_id": event["event_id"], "event_type": event["event_type"], "event_hash": event["event_hash"]},
                }]
            self._save_unlocked(state)
            return appended

    @staticmethod
    def _validate_execution_references(
        state: Mapping[str, Any],
        prior_events: list[dict[str, Any]],
        event: Mapping[str, Any],
    ) -> None:
        """Resolve new S06 references against this project's current records."""
        active_hashes: set[str] = set()
        for source in state.get("sources") or []:
            if not isinstance(source, Mapping) or source.get("status") == "deleted":
                continue
            recognition = source.get("recognition")
            artifact = recognition.get("artifact") if isinstance(recognition, Mapping) else None
            for content_hash in (
                source.get("content_hash"),
                artifact.get("content_hash") if isinstance(artifact, Mapping) else None,
            ):
                digest = str(content_hash or "").strip().lower()
                if re.fullmatch(r"[a-f0-9]{64}", digest):
                    active_hashes.add(digest)

        for reference in event.get("evidence_refs") or []:
            value = str(reference)
            prefix = "sha256:"
            digest = value[len(prefix):] if value.startswith(prefix) else ""
            if not re.fullmatch(r"[a-f0-9]{64}", digest) or digest not in active_hashes:
                raise ExecutionLedgerError("证据引用必须指向本项目当前有效来源的 SHA-256 内容哈希")

        prior_versions = {
            str(item.get("target_id", ""))
            for item in prior_events
            if item.get("event_type") == "RESULT_VERSIONED" and item.get("target_type") == "result_version"
        }
        for reference in event.get("result_version_refs") or []:
            value = str(reference)
            prefix = "result-version:"
            version_id = value[len(prefix):] if value.startswith(prefix) else ""
            if not version_id or version_id not in prior_versions:
                raise ExecutionLedgerError("结果版本引用必须指向本项目账本中更早登记的结果版本")

    def verify_execution_ledger(self, project_id: str) -> dict[str, Any]:
        """Verify one project's chain without changing project data."""
        snapshot = self.execution_ledger_snapshot(project_id)
        return {key: snapshot[key] for key in ("valid", "event_count", "last_event_hash")}

    def execution_ledger_snapshot(self, project_id: str) -> dict[str, Any]:
        """Read and verify one project's ledger under the project write lock."""
        with self._project_lock(project_id):
            state = self.load(project_id)
            if state is None:
                raise FileNotFoundError("项目尚未建立，不能校验运行记录")
            if str((state.get("project") or {}).get("id", "")) != project_id:
                raise ExecutionLedgerError("项目存储路径与项目编号不一致")
            ledger = [dict(item) for item in list(state.get("execution_ledger") or [])]
            last_hash = verify_execution_chain(ledger, project_id=project_id)
            return {
                "valid": True,
                "event_count": len(ledger),
                "last_event_hash": last_hash,
                "events": ledger,
                "agent_ops_plan_states": derive_agent_ops_plan_states(ledger),
            }

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
