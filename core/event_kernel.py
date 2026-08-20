"""Pure Engineering Event Kernel rules and deterministic distillation.

The kernel is deliberately independent from the filesystem, WebUI, plugins,
and external providers.  Adapters may give it local structured data or text;
the kernel returns traceable facts, an event draft, guards, and local rules.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


EVENT_STATUSES = (
    "DISCOVERED",
    "ASSESSED",
    "PLANNING",
    "COMMERCIAL_REVIEW",
    "DECIDED",
    "APPROVAL",
    "EXECUTING",
    "VERIFIED",
    "CLAIMING",
    "SETTLEMENT",
    "AUDITING",
    "COLLECTION",
    "CLOSED",
)

EVENT_SOURCE_TYPES = (
    "SITE_DISCOVERY",
    "DRAWING_REVIEW",
    "OWNER_INSTRUCTION",
    "DESIGN_CHANGE",
    "COST_VARIANCE",
    "QUANTITY_VARIANCE",
    "SCHEDULE_VARIANCE",
    "CONTRACT_REVIEW",
    "TECH_OPTIMIZATION",
    "AUDIT_FEEDBACK",
)

# These are the eight stable first-level classifications.  Tags remain open
# so a project may add its own vocabulary without changing the Core schema.
EVENT_TYPES = (
    "SITE_CONDITION",
    "DESIGN_CHANGE",
    "CONTRACT_REVIEW",
    "COST_VARIANCE",
    "QUANTITY_VARIANCE",
    "SCHEDULE_VARIANCE",
    "TECH_OPTIMIZATION",
    "AUDIT_FEEDBACK",
)

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
DIMENSIONS = ("cost", "revenue", "schedule", "quality", "safety")
THREE_EVIDENCE_TYPES = ("TECHNICAL", "PRODUCTION", "COMMERCIAL")

# Outcome is deliberately part of the Engineering Event Kernel, not a ninth
# capability.  It is the second, independent state machine: Event answers
# "what happened/was executed", while Outcome answers "what was converted
# into a realizable result".  The values below are snapshots of the owning
# P01-P08 records; they are never a second amount ledger.
OUTCOME_STATUSES = (
    "NOT_FORMED",
    "PHYSICAL_FORMED",
    "EVIDENCE_READY",
    "SUBMITTED",
    "CONFIRMED",
    "REVENUE_RECOGNIZED",
    "SETTLED",
    "CASH_REALIZED",
    "REJECTED",
    "ABANDONED",
)

OUTCOME_TYPES = ("PHYSICAL", "COMMERCIAL", "CONTRACTUAL", "SCHEDULE", "CASH")

OUTCOME_ALLOWED_TRANSITIONS = {
    "NOT_FORMED": {"PHYSICAL_FORMED", "REJECTED", "ABANDONED"},
    "PHYSICAL_FORMED": {"EVIDENCE_READY", "REJECTED", "ABANDONED"},
    "EVIDENCE_READY": {"SUBMITTED", "REJECTED", "ABANDONED"},
    "SUBMITTED": {"CONFIRMED", "REJECTED", "ABANDONED"},
    "CONFIRMED": {"REVENUE_RECOGNIZED", "SETTLED", "REJECTED", "ABANDONED"},
    "REVENUE_RECOGNIZED": {"SETTLED", "REJECTED", "ABANDONED"},
    "SETTLED": {"CASH_REALIZED", "REJECTED", "ABANDONED"},
    "CASH_REALIZED": set(),
    "REJECTED": set(),
    "ABANDONED": set(),
}

VALUE_LEAK_STAGES = (
    ("EVIDENCE_LEAK", "physical", "evidence_ready", "实体成果", "证据完整"),
    ("SUBMISSION_LEAK", "evidence_ready", "submitted", "证据完整", "已申报"),
    ("CONFIRMATION_LEAK", "submitted", "confirmed", "已申报", "已确认"),
    ("REVENUE_LEAK", "confirmed", "revenue", "已确认", "收入成立"),
    ("SETTLEMENT_LEAK", "revenue", "settled", "收入成立", "已结算"),
    ("CASH_LEAK", "settled", "paid", "已结算", "已回款"),
)

ALLOWED_TRANSITIONS = {
    "DISCOVERED": {"ASSESSED"},
    "ASSESSED": {"PLANNING"},
    "PLANNING": {"COMMERCIAL_REVIEW"},
    "COMMERCIAL_REVIEW": {"PLANNING", "DECIDED"},
    "DECIDED": {"APPROVAL"},
    "APPROVAL": {"EXECUTING"},
    "EXECUTING": {"VERIFIED"},
    "VERIFIED": {"CLAIMING"},
    "CLAIMING": {"SETTLEMENT"},
    "SETTLEMENT": {"AUDITING"},
    "AUDITING": {"COLLECTION"},
    "COLLECTION": {"CLOSED"},
    "CLOSED": set(),
}


class EventKernelError(ValueError):
    """Raised when an event violates the frozen kernel contract."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "approved", "已核验", "是"}


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def new_outcome_track(stamp: str = "") -> dict[str, Any]:
    """Return the minimal append-only Outcome projection for an Event."""
    stamp = stamp or _now()
    return {
        "status": "NOT_FORMED",
        "types": [],
        "title": "",
        "owner": "",
        # These are read-only snapshots of P01-P08 facts, not a second ledger.
        "values": {
            "physical": None,
            "evidence_ready": None,
            "submitted": None,
            "confirmed": None,
            "revenue": None,
            "settled": None,
            "paid": None,
        },
        "contractual_status": "PENDING",
        "schedule_days": None,
        "failure_reason": "",
        "leak_reasons": {},
        "references": [],
        "revisions": [],
        "status_history": [{"from": None, "to": "NOT_FORMED", "at": stamp}],
    }


def ensure_outcome_track(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with the Outcome projection migrated for old events."""
    candidate = deepcopy(dict(event))
    existing = candidate.get("outcome_track")
    if not isinstance(existing, Mapping):
        candidate["outcome_track"] = new_outcome_track(_text(_mapping(candidate.get("governance")).get("created_at")))
        return candidate
    outcome = dict(existing)
    defaults = new_outcome_track()
    for key, value in defaults.items():
        if key not in outcome:
            outcome[key] = deepcopy(value)
    values = dict(outcome.get("values") or {})
    values_defaults = defaults["values"]
    for key, value in values_defaults.items():
        values.setdefault(key, value)
    outcome["values"] = values
    outcome["types"] = [item for item in _list(outcome.get("types")) if _text(item) in OUTCOME_TYPES]
    outcome["status"] = _text(outcome.get("status")) or "NOT_FORMED"
    candidate["outcome_track"] = outcome
    return candidate


def _outcome_values(event: Mapping[str, Any]) -> dict[str, float | None]:
    outcome = _mapping(event.get("outcome_track"))
    raw = _mapping(outcome.get("values"))
    keys = {"physical"}
    for _, previous_key, next_key, *_ in VALUE_LEAK_STAGES:
        keys.update((previous_key, next_key))
    return {key: _number(raw.get(key)) for key in keys}


def compute_value_leaks(event: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the six value-conversion gaps without creating another ledger."""
    outcome = _mapping(event.get("outcome_track"))
    values = _outcome_values(event)
    reasons = _mapping(outcome.get("leak_reasons"))
    leaks: list[dict[str, Any]] = []
    total = 0.0
    for code, previous_key, next_key, previous_label, next_label in VALUE_LEAK_STAGES:
        previous = values.get(previous_key)
        current = values.get(next_key)
        if previous is None:
            continue
        amount = max(0.0, float(previous) - float(current or 0.0))
        if amount <= 0:
            continue
        total += amount
        leaks.append(
            {
                "code": code,
                "from_stage": previous_label,
                "to_stage": next_label,
                "amount": round(amount, 2),
                "reason": _text(reasons.get(code)) or "待补充原因",
                "event_id": _text(event.get("event_id")),
            }
        )
    return {
        "total": round(total, 2),
        "count": len(leaks),
        "items": leaks,
        "status": "LEAK" if leaks else "CLEAR",
        "local_only": True,
    }


def build_outcome_vector(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return an amount-free Outcome vector safe for role-limited views."""
    outcome = _mapping(event.get("outcome_track"))
    leaks = compute_value_leaks(event)
    types = [item for item in _list(outcome.get("types")) if _text(item) in OUTCOME_TYPES]
    first_leak = (leaks.get("items") or [{}])[0]
    return {
        "status": _text(outcome.get("status")) or "NOT_FORMED",
        "types": types,
        "contractual": _text(outcome.get("contractual_status")) or "PENDING",
        "schedule_days": _number(outcome.get("schedule_days")),
        "value_leak_count": int(leaks.get("count", 0) or 0),
        "value_leak_status": leaks.get("status", "CLEAR"),
        "pending_stage": first_leak.get("to_stage", "") if first_leak else "",
        "status_history_count": len(_list(outcome.get("status_history"))),
    }


def record_outcome_snapshot(
    event: Mapping[str, Any],
    changes: Mapping[str, Any],
    *,
    actor: Mapping[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Append a new Outcome snapshot while keeping prior values auditable."""
    candidate = ensure_outcome_track(event)
    outcome = candidate["outcome_track"]
    allowed = {"title", "owner", "types", "contractual_status", "schedule_days", "failure_reason", "leak_reasons", "references", "values"}
    unknown = sorted(str(key) for key in changes if str(key) not in allowed)
    if unknown:
        raise EventKernelError(f"Outcome 不支持字段：{'、'.join(unknown)}")
    before: dict[str, Any] = {}
    for key in changes:
        if key == "values":
            before["values"] = {str(value_key): deepcopy(value) for value_key, value in _mapping(outcome.get("values")).items() if value_key in _mapping(changes.get("values"))}
        else:
            before[key] = deepcopy(outcome.get(key))
    applied: dict[str, Any] = {}
    for key, value in changes.items():
        if key == "values":
            if not isinstance(value, Mapping):
                raise EventKernelError("Outcome values 必须是对象")
            current_values = dict(outcome.get("values") or {})
            for value_key, raw in value.items():
                if value_key not in current_values:
                    raise EventKernelError(f"Outcome 不支持价值字段：{value_key}")
                if raw not in (None, "") and (_number(raw) is None or float(_number(raw) or 0) < 0):
                    raise EventKernelError(f"Outcome 价值字段必须为非负数字：{value_key}")
                current_values[value_key] = None if raw in (None, "") else float(_number(raw) or 0)
            outcome["values"] = current_values
            applied["values"] = deepcopy(current_values)
        elif key == "types":
            types = [str(item).strip().upper() for item in _list(value) if str(item).strip()]
            invalid = [item for item in types if item not in OUTCOME_TYPES]
            if invalid:
                raise EventKernelError(f"Outcome 类型不受支持：{'、'.join(invalid)}")
            outcome["types"] = list(dict.fromkeys(types))
            applied[key] = list(outcome["types"])
        elif key == "references":
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
                raise EventKernelError("Outcome references 必须是数组")
            outcome["references"] = [dict(item) for item in value if isinstance(item, Mapping)]
            applied[key] = deepcopy(outcome["references"])
        elif key == "leak_reasons":
            if not isinstance(value, Mapping):
                raise EventKernelError("Outcome leak_reasons 必须是对象")
            outcome["leak_reasons"] = {str(k): str(v).strip() for k, v in value.items() if str(v).strip()}
            applied[key] = deepcopy(outcome["leak_reasons"])
        elif key == "schedule_days":
            if value not in (None, "") and (_number(value) is None or float(_number(value) or 0) < 0):
                raise EventKernelError("Outcome 工期影响必须为非负数字")
            outcome[key] = None if value in (None, "") else float(_number(value) or 0)
            applied[key] = outcome[key]
        else:
            outcome[key] = str(value).strip() if value is not None else ""
            applied[key] = outcome[key]
    revisions = list(outcome.get("revisions") or [])
    revisions.append(
        {
            "revision": len(revisions) + 1,
            "at": _now(),
            "actor": _text(_mapping(actor).get("username") or _mapping(actor).get("id")),
            "reason": _text(reason) or "Outcome 快照更新",
            "changes": applied,
            "before": before,
        }
    )
    outcome["revisions"] = revisions
    candidate.setdefault("governance", {})["updated_at"] = _now()
    return candidate


def transition_outcome(event: Mapping[str, Any], target_status: str, *, actor: Mapping[str, Any] | None = None, reason: str = "") -> dict[str, Any]:
    """Move the independent Outcome state machine through guarded commands."""
    candidate = ensure_outcome_track(event)
    outcome = candidate["outcome_track"]
    current = _text(outcome.get("status")) or "NOT_FORMED"
    target = _text(target_status).upper()
    if target not in OUTCOME_STATUSES:
        raise EventKernelError(f"不支持的 Outcome 状态：{target}")
    if target not in OUTCOME_ALLOWED_TRANSITIONS.get(current, set()):
        raise EventKernelError(f"不允许从 {current} 推进到 {target}")
    values = _mapping(outcome.get("values"))
    production = _mapping(event.get("production_track"))
    evidence = _mapping(_mapping(event.get("evidence")).get("three_evidence"))
    if target == "PHYSICAL_FORMED" and float(_number(production.get("progress")) or 0) < 100 and _number(values.get("physical")) is None:
        raise EventKernelError("实体成果尚未形成：生产进度需要达到 100% 或记录实体价值")
    if target == "EVIDENCE_READY" and _text(evidence.get("status")) != "PASS":
        raise EventKernelError("证据成果尚未形成：三证互证需要通过")
    required_values = {"SUBMITTED": "submitted", "CONFIRMED": "confirmed", "REVENUE_RECOGNIZED": "revenue", "SETTLED": "settled", "CASH_REALIZED": "paid"}
    value_key = required_values.get(target)
    if value_key and _number(values.get(value_key)) is None:
        raise EventKernelError(f"Outcome 尚未记录 {value_key} 快照金额")
    if target in {"REJECTED", "ABANDONED"} and not (_text(outcome.get("failure_reason")) or _text(reason)):
        raise EventKernelError("失败或放弃的 Outcome 必须记录原因")
    if reason:
        outcome["failure_reason"] = _text(reason)
    stamp = _now()
    history = list(outcome.get("status_history") or [])
    history.append({"from": current, "to": target, "at": stamp, "actor": _text(_mapping(actor).get("username") or _mapping(actor).get("id"))})
    outcome["status"] = target
    outcome["status_history"] = history
    candidate.setdefault("governance", {})["updated_at"] = stamp
    return candidate


def _fact(fact_id: str, kind: str, value: Any, source_refs: Sequence[str], confidence: float, origin: str) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "kind": kind,
        "value": deepcopy(value),
        "source_refs": list(dict.fromkeys(str(item) for item in source_refs if str(item).strip())),
        "confidence": round(float(confidence), 2),
        "origin": origin,
    }


def new_event(
    project_id: str,
    *,
    event_id: str = "",
    title: str,
    summary: str = "",
    source_type: str = "SITE_DISCOVERY",
    event_type: str = "SITE_CONDITION",
    severity: str = "MEDIUM",
    discovered_by: str = "",
    discovered_at: str = "",
    location: Mapping[str, Any] | None = None,
    tags: Sequence[str] = (),
    dimensions: Mapping[str, Any] | None = None,
    source_refs: Sequence[str] = (),
) -> dict[str, Any]:
    project_id = _text(project_id)
    title = _text(title)
    if not project_id or not title:
        raise EventKernelError("工程事件需要项目标识和标题")
    if source_type not in EVENT_SOURCE_TYPES:
        raise EventKernelError(f"不支持的事件来源类型：{source_type}")
    if event_type not in EVENT_TYPES:
        raise EventKernelError(f"不支持的事件分类：{event_type}")
    if severity not in SEVERITIES:
        raise EventKernelError(f"不支持的事件严重程度：{severity}")
    stamp = discovered_at or _now()
    event_id = _text(event_id) or f"EV-{datetime.now(timezone.utc).year}-{uuid4().hex[:8].upper()}"
    clean_dimensions = {key: _as_bool((_mapping(dimensions)).get(key)) for key in DIMENSIONS}
    clean_location = {key: _text((_mapping(location)).get(key)) for key in ("zone", "axis", "level", "place") if _text((_mapping(location)).get(key))}
    return {
        "event_id": event_id,
        "project_id": project_id,
        "status": "DISCOVERED",
        "identity": {
            "permanent_id": event_id,
            "title": title,
            "summary": _text(summary),
        },
        "origin": {
            "source_type": source_type,
            "discovered_at": stamp,
            "discovered_by": _text(discovered_by),
            "location": clean_location,
            "source_refs": list(dict.fromkeys(_text(item) for item in source_refs if _text(item))),
        },
        "classification": {
            "event_type": event_type,
            "tags": list(dict.fromkeys(_text(item) for item in tags if _text(item))),
            "severity": severity,
            "dimensions": clean_dimensions,
        },
        "baseline_impact": {
            "contract": {"affected": False, "baseline_id": "", "clause_refs": []},
            "price": {"affected": False, "baseline_id": "", "boq_refs": []},
            "quantity": {"affected": False, "baseline_id": "", "original_quantity": None, "current_estimate": None, "unit": ""},
            "cost": {"affected": False, "baseline_id": "", "baseline_cost": None, "forecast_cost": None},
        },
        "production_track": {
            "owner": "",
            "status": "NOT_STARTED",
            "progress": 0,
            "actual": {"start": "", "finish": "", "method": "", "workforce": "", "machinery": "", "materials": "", "quantity": None, "location": {}},
            "records": [],
        },
        "technical_track": {
            "owner": "",
            "status": "NOT_STARTED",
            "assessment": "",
            "needed": False,
            "drawing_refs": [],
            "spec_refs": [],
            "options": [],
        },
        "commercial_track": {
            "owner": "",
            "status": "NOT_STARTED",
            "evaluations": [],
            "claim_status": "NOT_CREATED",
        },
        "decision": {
            "status": "PENDING",
            "type": "",
            "selected_option_id": "",
            "result": "",
            "reason": "",
            "approvals": [],
        },
        "evidence": {
            "items": [],
            "claims": [],
            "three_evidence": {"technical": "NOT_STARTED", "production": "NOT_STARTED", "commercial": "NOT_STARTED", "status": "NOT_STARTED", "completeness": 0},
        },
        "settlement": {
            "measurement_status": "NOT_STARTED",
            "settlement_submitted": False,
            "estimated_revenue": None,
            "submitted_amount": None,
            "approved_measurement": None,
            "audit_1": None,
            "audit_2": None,
            "final_certified": None,
        },
        "audit_cash": {"audit_readiness": 0, "cash_status": "N/A", "cash_collected": None},
        "outcome_track": new_outcome_track(stamp),
        "governance": {
            "created_at": stamp,
            "updated_at": stamp,
            "responsibility": {},
            "external_approval": {"status": "NOT_REQUIRED", "approved_at": ""},
            "formal_basis": "",
            "emergency_override": False,
            "append_only": True,
            "status_history": [{"from": None, "to": "DISCOVERED", "at": stamp}],
        },
    }


def validate_event(event: Mapping[str, Any]) -> None:
    if not isinstance(event, Mapping):
        raise EventKernelError("工程事件必须是对象")
    for key in ("event_id", "project_id", "identity", "origin", "classification", "governance"):
        if not event.get(key):
            raise EventKernelError(f"工程事件缺少 {key}")
    status = _text(event.get("status") or _mapping(event.get("governance")).get("status") or "DISCOVERED")
    if status not in EVENT_STATUSES:
        raise EventKernelError(f"不支持的事件状态：{status}")
    identity = _mapping(event.get("identity"))
    classification = _mapping(event.get("classification"))
    if not _text(identity.get("title")):
        raise EventKernelError("工程事件缺少标题")
    if _text(classification.get("event_type")) not in EVENT_TYPES:
        raise EventKernelError("工程事件分类不在冻结的八类范围内")
    if _text(classification.get("severity")) not in SEVERITIES:
        raise EventKernelError("工程事件严重程度不受支持")
    outcome = _mapping(event.get("outcome_track"))
    if outcome:
        if _text(outcome.get("status")) not in OUTCOME_STATUSES:
            raise EventKernelError("Outcome 状态不受支持")
        invalid_types = [item for item in _list(outcome.get("types")) if _text(item) not in OUTCOME_TYPES]
        if invalid_types:
            raise EventKernelError("Outcome 类型不受支持")


def _status(event: Mapping[str, Any]) -> str:
    return _text(event.get("status") or _mapping(event.get("governance")).get("status") or "DISCOVERED")


def _set_status(event: dict[str, Any], status: str) -> None:
    event["status"] = status
    governance = event.setdefault("governance", {})
    governance["status"] = status
    governance["updated_at"] = _now()


def _guard_errors(event: Mapping[str, Any], current: str, target: str) -> list[str]:
    errors: list[str] = []
    identity = _mapping(event.get("identity"))
    origin = _mapping(event.get("origin"))
    classification = _mapping(event.get("classification"))
    baseline = _mapping(event.get("baseline_impact"))
    technical = _mapping(event.get("technical_track"))
    commercial = _mapping(event.get("commercial_track"))
    decision = _mapping(event.get("decision"))
    production = _mapping(event.get("production_track"))
    evidence = _mapping(event.get("evidence"))
    settlement = _mapping(event.get("settlement"))
    governance = _mapping(event.get("governance"))
    if current == "DISCOVERED" and target == "ASSESSED":
        required = {
            "事件说明": identity.get("summary"),
            "发现时间": origin.get("discovered_at"),
            "发现人": origin.get("discovered_by"),
            "发现位置": _mapping(origin.get("location")),
            "初始来源": _list(origin.get("source_refs")),
            "事件分类": classification.get("event_type"),
        }
        errors.extend(f"{label}未填写" for label, value in required.items() if not value)
    elif current == "ASSESSED" and target == "PLANNING":
        if not any(_as_bool(_mapping(value).get("affected")) for value in baseline.values()):
            errors.append("尚未标记受影响的合同、价格、数量或成本基线")
        if not any(_as_bool(value) for value in _mapping(classification.get("dimensions")).values()):
            errors.append("尚未标记成本、收入、工期、质量或安全影响维度")
        if not _as_bool(technical.get("needed")) and not _text(technical.get("assessment")):
            errors.append("尚未形成技术必要性判断")
    elif current == "PLANNING" and target == "COMMERCIAL_REVIEW":
        options = _list(technical.get("options"))
        feasible = [item for item in options if _as_bool(_mapping(item).get("feasible")) and all(_as_bool(_mapping(item).get(key)) for key in ("safety_pass", "quality_pass", "compliance_pass"))]
        if not feasible:
            errors.append("没有通过可行性、安全、质量和合规检查的技术方案")
    elif current == "COMMERCIAL_REVIEW" and target == "DECIDED":
        if not _list(commercial.get("evaluations")):
            errors.append("尚未形成技术方案对应的造价评价")
        if not _text(decision.get("selected_option_id")) and not _text(decision.get("type")):
            errors.append("尚未记录经营决策")
    elif current == "DECIDED" and target == "APPROVAL":
        if not _text(decision.get("selected_option_id")) and not _text(decision.get("type")):
            errors.append("缺少已选择方案或决策类型")
    elif current == "APPROVAL" and target == "EXECUTING":
        external = _mapping(governance.get("external_approval"))
        if not (_text(governance.get("formal_basis")) or _as_bool(governance.get("emergency_override")) or _text(external.get("status")) == "APPROVED"):
            errors.append("缺少正式执行依据或紧急授权记录")
    elif current == "EXECUTING" and target == "VERIFIED":
        if float(_number(production.get("progress")) or 0) < 100:
            errors.append("生产进度尚未达到 100%")
        if not _list(production.get("records")):
            errors.append("缺少生产实测或现场记录")
        if _text(technical.get("status")) not in {"APPROVED", "FEASIBLE", "COMPLETED"}:
            errors.append("技术线尚未确认实施结果")
    elif current == "VERIFIED" and target == "CLAIMING":
        three = _mapping(evidence.get("three_evidence"))
        if _text(three.get("status")) != "PASS" or any(_text(three.get(key)) != "PASS" for key in ("technical", "production", "commercial")):
            errors.append("技术证、生产证、造价证尚未通过三证互证")
    elif current == "CLAIMING" and target == "SETTLEMENT":
        if _text(commercial.get("claim_status")) not in {"CREATED", "SUBMITTED", "APPROVED"}:
            errors.append("尚未形成商务申报")
        if settlement.get("submitted_amount") in (None, ""):
            errors.append("尚未记录申报金额")
    elif current == "SETTLEMENT" and target == "AUDITING":
        if not _as_bool(settlement.get("settlement_submitted")):
            errors.append("尚未提交结算资料")
    elif current == "AUDITING" and target == "COLLECTION":
        if settlement.get("final_certified") in (None, ""):
            errors.append("尚未形成最终审定金额")
    elif current == "COLLECTION" and target == "CLOSED":
        cash = _text(_mapping(event.get("audit_cash")).get("cash_status"))
        if cash not in {"COLLECTED", "N/A", "CLOSED"}:
            errors.append("资金回收尚未关闭，或未声明无需回收")
    return errors


def transition_event(event: Mapping[str, Any], target_status: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    candidate = deepcopy(dict(event))
    validate_event(candidate)
    current = _status(candidate)
    target_status = _text(target_status)
    if target_status not in EVENT_STATUSES:
        raise EventKernelError(f"不支持的目标状态：{target_status}")
    if target_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise EventKernelError(f"不允许从 {current} 推进到 {target_status}")
    errors = _guard_errors(candidate, current, target_status)
    if errors:
        raise EventKernelError("；".join(errors))
    stamp = _now()
    governance = candidate.setdefault("governance", {})
    history = list(governance.get("status_history") or [])
    history.append({"from": current, "to": target_status, "at": stamp, "actor": _text(_mapping(actor).get("username") or _mapping(actor).get("id"))})
    governance["status_history"] = history
    _set_status(candidate, target_status)
    return candidate


def build_state_vector(event: Mapping[str, Any]) -> dict[str, Any]:
    production = _mapping(event.get("production_track"))
    technical = _mapping(event.get("technical_track"))
    commercial = _mapping(event.get("commercial_track"))
    evidence = _mapping(event.get("evidence"))
    three = _mapping(evidence.get("three_evidence"))
    governance = _mapping(event.get("governance"))
    settlement = _mapping(event.get("settlement"))
    audit_cash = _mapping(event.get("audit_cash"))
    outcome_vector = build_outcome_vector(event)
    return {
        "event": _status(event),
        "production": round(float(_number(production.get("progress")) or 0), 1),
        "technical": _text(technical.get("status")) or "NOT_STARTED",
        "commercial": _text(commercial.get("status")) or "NOT_STARTED",
        "evidence": round(float(_number(three.get("completeness")) or 0), 1),
        "external_approval": _text(_mapping(governance.get("external_approval")).get("status")) or "NOT_REQUIRED",
        "measurement": _text(settlement.get("measurement_status")) or "NOT_STARTED",
        "audit_readiness": round(float(_number(audit_cash.get("audit_readiness")) or 0), 1),
        "cash": _text(audit_cash.get("cash_status")) or "N/A",
        "risk": _text(_mapping(event.get("classification")).get("severity")) or "MEDIUM",
        "three_evidence": _text(three.get("status")) or "NOT_STARTED",
        "outcome": outcome_vector["status"],
        "outcome_types": outcome_vector["types"],
        "outcome_pending_stage": outcome_vector["pending_stage"],
        "value_leak_count": outcome_vector["value_leak_count"],
        "value_leak_status": outcome_vector["value_leak_status"],
    }


def evaluate_event_rules(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    production = _mapping(event.get("production_track"))
    commercial = _mapping(event.get("commercial_track"))
    technical = _mapping(event.get("technical_track"))
    evidence = _mapping(event.get("evidence"))
    three = _mapping(evidence.get("three_evidence"))
    settlement = _mapping(event.get("settlement"))
    audit_cash = _mapping(event.get("audit_cash"))
    outcome = _mapping(ensure_outcome_track(event).get("outcome_track"))
    alerts: list[dict[str, Any]] = []

    def add(rule_id: str, severity: str, title: str, message: str) -> None:
        alerts.append({"rule_id": rule_id, "severity": severity, "title": title, "message": message, "local_only": True})

    progress = float(_number(production.get("progress")) or 0)
    evidence_completeness = float(_number(three.get("completeness")) or 0)
    if progress >= 100 and _text(commercial.get("claim_status")) in {"", "NOT_CREATED"}:
        add("EVENT-COMMERCIAL-01", "warn", "已完工但未形成商务申报", "生产线已完成，商务申报仍未创建。")
    if progress > 50 and evidence_completeness < 40:
        add("EVENT-EVIDENCE-01", "block", "证据形成严重滞后", f"生产进度 {progress:g}%；三证完整度仅 {evidence_completeness:g}%。")
    expected_profit = _number(commercial.get("expected_profit"))
    if expected_profit is None:
        evaluations = _list(commercial.get("evaluations"))
        expected_profit = next((_number(_mapping(item).get("expected_profit")) for item in evaluations if _number(_mapping(item).get("expected_profit")) is not None), None)
    if expected_profit is not None and expected_profit > 0 and _text(technical.get("status")) not in {"APPROVED", "FEASIBLE", "COMPLETED"}:
        add("EVENT-TECHNICAL-01", "warn", "盈利方案尚不具备实施条件", "已有正向利润测算，但技术审批尚未通过。")
    if settlement.get("submitted_amount") not in (None, "") and _text(three.get("status")) != "PASS":
        add("EVENT-AUDIT-01", "block", "结算申报缺少三证互证", "已提交结算金额，但技术证、生产证、造价证尚未全部通过。")
    final_certified = _number(settlement.get("final_certified"))
    cash_collected = _number(audit_cash.get("cash_collected")) or 0
    if final_certified is not None and final_certified > cash_collected:
        add("EVENT-CASH-01", "warn", "审定金额尚未全部回收", f"审定金额 {final_certified:g} 高于已回收金额 {cash_collected:g}。")
    outcome_vector = build_outcome_vector(event)
    if progress >= 100 and _text(outcome.get("status")) == "NOT_FORMED":
        add("OUTCOME-01", "warn", "实体完成但尚未形成成果", "生产已完成，Outcome 仍未进入实体成果状态。")
    if outcome_vector["value_leak_count"]:
        severity = "block" if _text(_mapping(event.get("classification")).get("severity")) == "CRITICAL" else "warn"
        add("OUTCOME-LEAK-01", severity, "经营成果存在价值转化缺口", f"当前有 {outcome_vector['value_leak_count']} 个成果转化阶段存在差额，请沿 Outcome → 造价事实核对。")
    if _text(outcome.get("status")) in {"REJECTED", "ABANDONED"}:
        add("OUTCOME-FAIL-01", "info", "Outcome 未实现", "该成果已被拒绝或放弃；保留历史并记录原因，不删除 Event。")
    return alerts


def _event_type_from_text(text: str) -> str:
    mappings = (
        (("地下", "障碍", "地质", "现场条件"), "SITE_CONDITION"),
        (("设计变更", "图纸变更", "变更"), "DESIGN_CHANGE"),
        (("合同", "条款", "索赔"), "CONTRACT_REVIEW"),
        (("超支", "成本", "价格", "费用"), "COST_VARIANCE"),
        (("工程量", "数量", "超量", "少量"), "QUANTITY_VARIANCE"),
        (("工期", "延误", "进度"), "SCHEDULE_VARIANCE"),
        (("优化", "技术方案", "施工方案"), "TECH_OPTIMIZATION"),
        (("审计", "结算", "复核"), "AUDIT_FEEDBACK"),
    )
    for terms, event_type in mappings:
        if any(term in text for term in terms):
            return event_type
    return "SITE_CONDITION"


def _source_type_from_text(text: str, event_type: str) -> str:
    if "业主" in text or "发包人" in text:
        return "OWNER_INSTRUCTION"
    if "图纸" in text:
        return "DRAWING_REVIEW"
    return {"DESIGN_CHANGE": "DESIGN_CHANGE", "COST_VARIANCE": "COST_VARIANCE", "QUANTITY_VARIANCE": "QUANTITY_VARIANCE", "SCHEDULE_VARIANCE": "SCHEDULE_VARIANCE", "TECH_OPTIMIZATION": "TECH_OPTIMIZATION", "CONTRACT_REVIEW": "CONTRACT_REVIEW", "AUDIT_FEEDBACK": "AUDIT_FEEDBACK"}.get(event_type, "SITE_DISCOVERY")


def _text_dimensions(text: str) -> dict[str, bool]:
    return {
        "cost": any(term in text for term in ("成本", "价格", "费用", "金额", "造价")),
        "revenue": any(term in text for term in ("收入", "索赔", "计价", "结算", "签证")),
        "schedule": any(term in text for term in ("工期", "延误", "进度", "日期")),
        "quality": any(term in text for term in ("质量", "验收", "规范")),
        "safety": any(term in text for term in ("安全", "危险", "风险", "隐患")),
    }


def distill_text(text: str, source_ref: str = "text-input", project_id: str = "") -> dict[str, Any]:
    """Extract conservative facts from user text without calling an AI provider."""
    normalized = " ".join(_text(text).split())
    if not normalized:
        return {"origin": "DISTILLED_TEXT", "facts": [], "claims": [], "suggested_event": None, "summary": {"fact_count": 0, "claim_count": 0}, "local_only": True}
    event_type = _event_type_from_text(normalized)
    source_type = _source_type_from_text(normalized, event_type)
    severity = "HIGH" if any(term in normalized for term in ("紧急", "重大", "安全事故", "严重", "立即")) else "MEDIUM"
    facts = [
        _fact("TEXT-001", "classification.event_type", event_type, [source_ref], 0.78, "DISTILLED_TEXT"),
        _fact("TEXT-002", "origin.source_type", source_type, [source_ref], 0.72, "DISTILLED_TEXT"),
        _fact("TEXT-003", "classification.severity", severity, [source_ref], 0.68, "DISTILLED_TEXT"),
        _fact("TEXT-004", "classification.dimensions", _text_dimensions(normalized), [source_ref], 0.74, "DISTILLED_TEXT"),
    ]
    numbers = re.findall(r"\d+(?:\.\d+)?\s*(?:m3|m²|㎡|立方米|平方米|元|万元|天|日|%)?", normalized, flags=re.IGNORECASE)
    if numbers:
        facts.append(_fact("TEXT-005", "quantities_or_amounts", numbers[:12], [source_ref], 0.65, "DISTILLED_TEXT"))
    dates = re.findall(r"(?:20\d{2}[-年/.])\d{1,2}(?:[-月/.])\d{1,2}日?", normalized)
    if dates:
        facts.append(_fact("TEXT-006", "time.references", dates[:8], [source_ref], 0.82, "DISTILLED_TEXT"))
    locations = re.findall(r"(?:位置|部位|区域|桩号|楼层|地点)[:：]?([^，。；;]{2,30})", normalized)
    if locations:
        facts.append(_fact("TEXT-007", "origin.location", locations[:5], [source_ref], 0.62, "DISTILLED_TEXT"))
    sentences = [item.strip() for item in re.split(r"[。；;!?！？\n]+", normalized) if item.strip()]
    claims = [item for item in sentences if any(term in item for term in ("应", "需要", "影响", "预计", "增加", "减少", "变更", "延误", "必须", "建议"))][:8]
    claim_items = [{"claim_id": f"CL-TEXT-{index:03d}", "text": claim, "source_refs": [source_ref], "status": "UNVERIFIED", "origin": "DISTILLED_TEXT"} for index, claim in enumerate(claims, start=1)]
    title = sentences[0][:80] if sentences else "文本识别工程事件"
    suggestion = new_event(
        project_id or "local-project",
        event_id="",
        title=title,
        summary=normalized[:300],
        source_type=source_type,
        event_type=event_type,
        severity=severity,
        source_refs=[source_ref],
        dimensions=_text_dimensions(normalized),
    )
    return {
        "origin": "DISTILLED_TEXT",
        "source_ref": source_ref,
        "facts": facts,
        "claims": claim_items,
        "suggested_event": suggestion,
        "summary": {"fact_count": len(facts), "claim_count": len(claim_items), "number_count": len(numbers), "local_only": True},
        "local_only": True,
        "external_sent": False,
    }


def distill_local_data(workspace: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize existing P01-P08 records into traceable local facts."""
    project = _mapping(workspace.get("project"))
    project_id = _text(project.get("id"))
    facts: list[dict[str, Any]] = []
    source_refs = [_text(item.get("source_id")) or _text(item.get("name")) for item in _list(workspace.get("sources")) if isinstance(item, Mapping)]
    source_refs = [item for item in source_refs if item]
    index = 0

    def add(kind: str, value: Any, refs: Sequence[str] = (), confidence: float = 0.95) -> None:
        nonlocal index
        index += 1
        facts.append(_fact(f"LOCAL-{index:03d}", kind, value, list(refs) or source_refs[:8], confidence, "LOCAL_PROJECT"))

    add("project.identity", {"project_id": project_id, "name": _text(project.get("name"))}, [], 1.0)
    add("project.source_count", len(source_refs), source_refs, 1.0)
    stage_names = {
        "contract": "P01 合同与招采依据",
        "boq": "P02 清单资料",
        "drawings": "P03 图纸资料",
        "baseline": "P04 零号台账",
        "cost_plan": "P05 成本计划",
        "changes": "P06 变更管理",
        "evidence": "P07 证据关联",
        "review": "P08 结算初审",
    }
    candidate_events: list[dict[str, Any]] = []
    for stage, label in stage_names.items():
        container = _mapping(workspace.get(stage))
        result = _mapping(container.get("result")) if container else {}
        if not result:
            continue
        summary = _mapping(result.get("summary"))
        add(f"{stage}.summary", {"label": label, "summary": dict(summary)}, [], 0.99)
        if stage == "changes":
            for change in _list(result.get("changes")):
                if not isinstance(change, Mapping):
                    continue
                ref = _text(change.get("source_id")) or f"P06:{_text(change.get('change_id'))}"
                add("change.observation", {"change_id": _text(change.get("change_id")), "title": _text(change.get("title")), "status": _text(change.get("status")), "amount": change.get("amount")}, [ref], 0.98)
                candidate_events.append({
                    "title": _text(change.get("title")) or "P06 变更事项",
                    "summary": _text(change.get("reason")) or "由本地 P06 变更记录蒸馏",
                    "source_type": "DESIGN_CHANGE",
                    "event_type": "DESIGN_CHANGE",
                    "severity": "HIGH" if _text(change.get("status")) == "pending" else "MEDIUM",
                    "source_refs": [ref],
                    "dimensions": {"cost": bool(change.get("amount")), "revenue": bool(change.get("amount")), "schedule": False, "quality": False, "safety": False},
                })
    recognition_pending = sum(1 for item in _list(workspace.get("sources")) if isinstance(item, Mapping) and _text(_mapping(item.get("recognition")).get("status")) not in {"recognized", "supported", "completed"})
    if recognition_pending:
        add("sources.recognition_pending", recognition_pending, source_refs, 0.99)
    if not candidate_events:
        candidate_events.append({
            "title": "从本地 P01–P08 资料建立首个工程事件",
            "summary": "请补充现场事实、受影响基线和初始证据后再保存。",
            "source_type": "SITE_DISCOVERY",
            "event_type": "SITE_CONDITION",
            "severity": "MEDIUM",
            "source_refs": source_refs[:3],
            "dimensions": {key: False for key in DIMENSIONS},
        })
    return {
        "origin": "LOCAL_PROJECT",
        "project_id": project_id,
        "facts": facts,
        "candidate_events": candidate_events[:12],
        "source_refs": list(dict.fromkeys(source_refs)),
        "summary": {"fact_count": len(facts), "source_count": len(source_refs), "candidate_event_count": len(candidate_events), "local_only": True},
        "local_only": True,
        "external_sent": False,
    }


def fuse_distillations(local: Mapping[str, Any], text: Mapping[str, Any], project_id: str = "") -> dict[str, Any]:
    """Fuse local structure and text while keeping conflicts visible.

    Structured local project records win only for the same fact kind; text is
    retained as a separately sourced fact everywhere else.
    """
    local_facts = [dict(item) for item in _list(local.get("facts")) if isinstance(item, Mapping)]
    text_facts = [dict(item) for item in _list(text.get("facts")) if isinstance(item, Mapping)]
    local_by_kind = {str(item.get("kind")): item for item in local_facts}
    fused = list(local_facts)
    conflicts: list[dict[str, Any]] = []
    for item in text_facts:
        kind = str(item.get("kind", ""))
        local_item = local_by_kind.get(kind)
        if local_item is not None and local_item.get("value") != item.get("value"):
            conflicts.append({"kind": kind, "local": deepcopy(local_item.get("value")), "text": deepcopy(item.get("value")), "resolution": "保留本地结构化事实；文本事实保留为待核对"})
            item["status"] = "CONFLICT"
        fused.append(item)
    local_candidate = (_list(local.get("candidate_events")) or [None])[0]
    text_candidate = text.get("suggested_event") if isinstance(text.get("suggested_event"), Mapping) else None
    candidate = dict(text_candidate or {})
    if local_candidate:
        for key, value in dict(local_candidate).items():
            if key not in candidate or not candidate.get(key):
                candidate[key] = deepcopy(value)
        candidate["source_refs"] = list(dict.fromkeys([*_list(candidate.get("source_refs")), *_list(local_candidate.get("source_refs"))]))
    if not candidate:
        candidate = new_event(project_id or _text(local.get("project_id")) or "local-project", title="待建立工程事件")
    else:
        candidate.setdefault("project_id", project_id or _text(local.get("project_id")) or "local-project")
    claims = [dict(item) for item in _list(text.get("claims")) if isinstance(item, Mapping)]
    return {
        "origin": "FUSED_LOCAL_TEXT",
        "local_only": True,
        "external_sent": False,
        "facts": fused,
        "fused_facts": fused,
        "claims": claims,
        "conflicts": conflicts,
        "suggested_event": candidate,
        "summary": {
            "local_fact_count": len(local_facts),
            "text_fact_count": len(text_facts),
            "fused_fact_count": len(fused),
            "conflict_count": len(conflicts),
            "claim_count": len(claims),
        },
    }


def run_cross_check(event: Mapping[str, Any]) -> dict[str, Any]:
    """Run deterministic three-evidence and fact-consistency checks."""
    origin = _mapping(event.get("origin"))
    production = _mapping(event.get("production_track"))
    actual = _mapping(production.get("actual"))
    baseline_quantity = _mapping(_mapping(event.get("baseline_impact")).get("quantity"))
    technical = _mapping(event.get("technical_track"))
    checks: list[dict[str, Any]] = []

    def check(check_id: str, label: str, status: str, reason: str) -> None:
        checks.append({"check_id": check_id, "label": label, "status": status, "reason": reason})

    origin_location = _mapping(origin.get("location"))
    actual_location = _mapping(actual.get("location"))
    location_pairs = [(key, _text(origin_location.get(key)), _text(actual_location.get(key))) for key in ("zone", "axis", "level", "place") if _text(origin_location.get(key)) and _text(actual_location.get(key))]
    if location_pairs and any(left != right for _, left, right in location_pairs):
        check("LOCATION", "位置一致性", "CONFLICT", "发现位置与生产记录位置不一致。")
    else:
        check("LOCATION", "位置一致性", "PASS", "未发现位置冲突。")

    approval_times = [_text(_mapping(item).get("at")) for item in _list(_mapping(event.get("decision")).get("approvals")) if _text(_mapping(item).get("at"))]
    start = _text(actual.get("start"))
    if start and approval_times and start < min(approval_times):
        check("TIME", "批准与执行时间", "WARN", "生产开始时间早于批准记录，需要确认是否属于紧急授权。")
    else:
        check("TIME", "批准与执行时间", "PASS", "未发现执行早于批准的时间冲突。")

    original = _number(baseline_quantity.get("original_quantity"))
    measured = _number(actual.get("quantity"))
    if original is not None and measured is not None and abs(original - measured) > max(0.01, abs(original) * 0.01):
        check("QUANTITY", "工程量一致性", "CONFLICT", f"基线工程量 {original:g} 与生产实测 {measured:g} 不一致，需要解释差异。")
    else:
        check("QUANTITY", "工程量一致性", "PASS", "未发现工程量冲突。")

    method = _text(actual.get("method"))
    assessment = _text(technical.get("assessment"))
    if method and assessment and not any(token in assessment for token in method.split()):
        check("METHOD", "施工方法一致性", "WARN", "施工记录与技术判断缺少可直接对应的施工方法说明。")
    else:
        check("METHOD", "施工方法一致性", "PASS", "施工方法具备对应说明或尚未填写。")

    drawing_refs = {_text(item.get("drawing_no") or item.get("ref")) + "|" + _text(item.get("revision")) for item in _list(technical.get("drawing_refs")) if isinstance(item, Mapping)}
    if any("|" in item and item.endswith("|") for item in drawing_refs):
        check("DRAWING_VERSION", "图纸版本一致性", "WARN", "图纸引用没有完整版本号，存在审计风险。")
    else:
        check("DRAWING_VERSION", "图纸版本一致性", "PASS", "未发现图纸版本冲突。")
    three = _mapping(_mapping(event.get("evidence")).get("three_evidence"))
    check("THREE_EVIDENCE", "三证互证", "PASS" if _text(three.get("status")) == "PASS" else "PENDING", "技术证、生产证、造价证已全部通过。" if _text(three.get("status")) == "PASS" else "三证尚未全部通过。")
    conflicts = sum(item["status"] == "CONFLICT" for item in checks)
    warnings = sum(item["status"] in {"WARN", "PENDING"} for item in checks)
    return {"checks": checks, "status": "CONFLICT" if conflicts else "WARN" if warnings else "PASS", "conflict_count": conflicts, "warning_count": warnings}
