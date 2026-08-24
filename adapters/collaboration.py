"""Local coordination and relationship records.

This is an adapter-owned work-management projection.  It references existing
events, sources and P01-P08/Outcome paths; it does not own quantities,
amounts, or professional facts.  Every decision is a human-authored record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


TASK_STATUSES = ("OPEN", "IN_REVIEW", "WAITING_CONFIRMATION", "APPROVED", "REJECTED", "CLOSED")
DECISION_TYPES = ("GO", "OPTIMIZE", "HOLD", "REJECT")
DECISION_STATUSES = ("PROPOSED", "CONFIRMED", "REJECTED")
RELATION_TYPES = (
    "EVENT_TO_SOURCE",
    "EVENT_TO_TASK",
    "EVENT_TO_PERSON",
    "EVENT_TO_CAPABILITY",
    "EVENT_TO_OUTCOME",
    "EVENT_PARENT",
    "EVENT_SPLIT_FROM",
    "EVENT_CANCELLED_BY",
)
ROLE_IDS = ("production", "technical", "cost", "project_manager", "owner", "supervision", "audit")


class CoordinationError(ValueError):
    pass


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def new_task(project_id: str, payload: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    title = _text(payload.get("title"))
    if not title:
        raise CoordinationError("协同任务需要标题")
    role = _text(payload.get("role")).lower()
    if role not in ROLE_IDS:
        raise CoordinationError("协同任务需要有效责任线")
    event_id = _text(payload.get("event_id"))
    if not event_id:
        raise CoordinationError("协同任务必须关联 Core Event")
    username = _text(actor.get("username") or actor.get("id"))
    return {
        "task_id": _id("TASK"),
        "project_id": project_id,
        "title": title,
        "description": _text(payload.get("description")),
        "role": role,
        "assignee": _text(payload.get("assignee")),
        "event_id": event_id,
        "target_path": _text(payload.get("target_path")),
        "due_at": _text(payload.get("due_at")),
        "basis_refs": [_text(item) for item in (payload.get("basis_refs") or []) if _text(item)],
        "status": "OPEN",
        "created_by": username,
        "created_at": _now(),
        "history": [{"from": None, "to": "OPEN", "at": _now(), "actor": username}],
    }

def update_task(task: Mapping[str, Any], status: str, actor: Mapping[str, Any], note: str = "") -> dict[str, Any]:
    status = _text(status).upper()
    if status not in TASK_STATUSES:
        raise CoordinationError(f"不支持的协同任务状态：{status}")
    current = _text(task.get("status")) or "OPEN"
    if current == "CLOSED" and status != "CLOSED":
        raise CoordinationError("已关闭协同任务不可回退")
    result = dict(task)
    result["status"] = status
    result["updated_at"] = _now()
    result.setdefault("history", []).append({"from": current, "to": status, "at": _now(), "actor": _text(actor.get("username") or actor.get("id")), "note": _text(note)})
    return result


def new_decision(project_id: str, payload: Mapping[str, Any], actor: Mapping[str, Any], *, confirm: bool = False) -> dict[str, Any]:
    event_id = _text(payload.get("event_id"))
    decision_type = _text(payload.get("decision_type")).upper()
    reason = _text(payload.get("reason"))
    if not event_id:
        raise CoordinationError("决策必须关联 Core Event")
    if decision_type not in DECISION_TYPES:
        raise CoordinationError("决策类型只能是 GO、OPTIMIZE、HOLD 或 REJECT")
    if not reason:
        raise CoordinationError("决策必须记录依据/理由")
    username = _text(actor.get("username") or actor.get("id"))
    stamp = _now()
    return {
        "decision_id": _id("DEC"),
        "project_id": project_id,
        "event_id": event_id,
        "decision_type": decision_type,
        "reason": reason,
        "option_id": _text(payload.get("option_id")),
        "basis_refs": [_text(item) for item in (payload.get("basis_refs") or []) if _text(item)],
        "status": "CONFIRMED" if confirm else "PROPOSED",
        "human_confirmed": bool(confirm),
        "confirmed_by": username if confirm else "",
        "confirmed_at": stamp if confirm else "",
        "created_by": username,
        "created_at": stamp,
        "note": _text(payload.get("note")),
    }


def confirm_decision(decision: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    if _text(decision.get("status")) == "CONFIRMED":
        return dict(decision)
    username = _text(actor.get("username") or actor.get("id"))
    if not username:
        raise CoordinationError("决策确认必须有登录人员")
    result = dict(decision)
    result.update({"status": "CONFIRMED", "human_confirmed": True, "confirmed_by": username, "confirmed_at": _now()})
    return result


def new_relation(project_id: str, payload: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    relation_type = _text(payload.get("relation_type")).upper()
    from_id = _text(payload.get("from_id"))
    to_id = _text(payload.get("to_id"))
    if relation_type not in RELATION_TYPES:
        raise CoordinationError("关系类型不受支持")
    if not from_id or not to_id:
        raise CoordinationError("关系需要起点和终点标识")
    username = _text(actor.get("username") or actor.get("id"))
    return {
        "relation_id": _id("REL"),
        "project_id": project_id,
        "relation_type": relation_type,
        "from_type": _text(payload.get("from_type")) or "event",
        "from_id": from_id,
        "to_type": _text(payload.get("to_type")) or "event",
        "to_id": to_id,
        "label": _text(payload.get("label")),
        "basis_refs": [_text(item) for item in (payload.get("basis_refs") or []) if _text(item)],
        "created_by": username,
        "created_at": _now(),
        "append_only": True,
    }


def coordination_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable UI packet with explicit human-confirmation counts."""
    collaboration = state.get("collaboration") if isinstance(state.get("collaboration"), Mapping) else {}
    tasks = [dict(item) for item in collaboration.get("tasks") or [] if isinstance(item, Mapping)]
    decisions = [dict(item) for item in collaboration.get("decisions") or [] if isinstance(item, Mapping)]
    relations = [dict(item) for item in state.get("relationships") or [] if isinstance(item, Mapping)]
    adaptations = [dict(item) for item in state.get("line_adaptations") or [] if isinstance(item, Mapping)]
    return {
        "workflow": {
            "tasks": tasks,
            "task_counts": {status: sum(1 for item in tasks if _text(item.get("status")) == status) for status in TASK_STATUSES},
            "decisions": decisions,
            "decision_counts": {status: sum(1 for item in decisions if _text(item.get("status")) == status) for status in DECISION_STATUSES},
        },
        "relationships": relations,
        "line_adaptations": adaptations,
        "catalog": {"task_statuses": list(TASK_STATUSES), "decision_types": list(DECISION_TYPES), "decision_statuses": list(DECISION_STATUSES), "relation_types": list(RELATION_TYPES), "role_ids": list(ROLE_IDS)},
        "rules": {
            "human_confirmation_required": True,
            "data_is_evidence_not_decision": True,
            "references_existing_event_and_capabilities": True,
            "append_only_relations": True,
            "no_new_amount_ledger": True,
        },
    }
