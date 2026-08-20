"""Production / technical / cost line contracts and guarded adapters.

The adapters are deliberately boring: they validate, normalize and produce a
traceable mapping packet for the existing Core event and P01-P08 records.  No
adapter makes a business decision.  A record stays ``PENDING_CONFIRMATION``
until a named human confirms it; only then may the server apply the mapping to
an existing event.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


LINE_IDS = ("production", "technical", "cost")
LINE_LABELS = {
    "production": "生产线",
    "technical": "技术线",
    "cost": "造价线",
}

CONTRACT_VERSION = "1.0"

# The responsibility line is derived from the submitted business line.  It is
# deliberately not user-editable: only the corresponding department head may
# confirm a line packet and thereby change the Core projection.
LINE_HEAD_ROLES = {
    "production": "production_manager",
    "technical": "technical_lead",
    "cost": "cost_manager",
}
LINE_HEAD_LABELS = {
    "production": "生产负责人",
    "technical": "技术负责人",
    "cost": "造价经理",
}

LINE_CONTRACTS: dict[str, dict[str, Any]] = {
    "production": {
        "line": "production",
        "label": LINE_LABELS["production"],
        "version": CONTRACT_VERSION,
        "required": ("record_id", "project_id", "event_id", "occurred_at", "actor", "status", "progress", "evidence_refs"),
        "optional": ("quantity", "unit", "location", "method", "workforce", "machinery", "materials", "actual_start", "actual_finish"),
        "maps_to": ("Core.event.production_track", "Core.event.origin.source_refs", "P07.evidence"),
        "human_confirmation": "现场/生产负责人确认进度、实测量和证据引用",
    },
    "technical": {
        "line": "technical",
        "label": LINE_LABELS["technical"],
        "version": CONTRACT_VERSION,
        "required": ("record_id", "project_id", "event_id", "occurred_at", "actor", "status", "assessment", "evidence_refs"),
        "optional": ("drawing_refs", "spec_refs", "option_id", "feasible", "safety_pass", "quality_pass", "compliance_pass", "recommendation"),
        "maps_to": ("Core.event.technical_track", "P03.drawings", "P07.evidence"),
        "human_confirmation": "技术负责人确认图纸、规范、可行性和实施方案",
    },
    "cost": {
        "line": "cost",
        "label": LINE_LABELS["cost"],
        "version": CONTRACT_VERSION,
        "required": ("record_id", "project_id", "event_id", "occurred_at", "actor", "status", "evidence_refs", "basis_refs"),
        "optional": ("boq_refs", "quantity", "unit", "unit_price", "amount", "baseline_amount", "forecast_amount", "expected_profit", "claim_status", "recommendation"),
        "maps_to": ("Core.event.commercial_track", "P04.baseline", "P05.cost_plan", "P06.changes", "P08.review", "Outcome.values"),
        "human_confirmation": "造价负责人确认清单、依据、计价口径和金额快照",
    },
}


class LineContractError(ValueError):
    """Raised when a line payload is incomplete or bypasses confirmation."""


def line_responsibility(line: str) -> dict[str, Any]:
    """Return the deterministic responsibility policy for one business line."""
    normalized = _text(line).lower()
    if normalized not in LINE_HEAD_ROLES:
        raise LineContractError(f"不支持的责任线：{normalized}")
    return {
        "line": normalized,
        "head_role": LINE_HEAD_ROLES[normalized],
        "head_label": LINE_HEAD_LABELS[normalized],
        "assignment_mode": "AUTOMATIC_POLICY",
        "modifiable_by_roles": [LINE_HEAD_ROLES[normalized]],
    }


def _actor_roles(actor: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(actor, Mapping):
        return set()
    roles = actor.get("roles")
    if isinstance(roles, Sequence) and not isinstance(roles, (str, bytes, bytearray)):
        result = {_text(item) for item in roles if _text(item)}
    else:
        result = set()
    role = _text(actor.get("role"))
    if role:
        result.add(role)
    return result


def can_confirm_line(line: str, actor: Mapping[str, Any] | None) -> bool:
    """Only the mapped department head can modify/confirm that line."""
    return line_responsibility(line)["head_role"] in _actor_roles(actor)


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: object, field: str, *, non_negative: bool = True) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise LineContractError(f"{field} 必须是数字") from exc
    if non_negative and number < 0:
        raise LineContractError(f"{field} 不能为负数")
    return number


def _list(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value]
    if value in (None, ""):
        return []
    return [_text(value)]


def _stamp(value: object) -> str:
    raw = _text(value)
    if not raw:
        raise LineContractError("occurred_at 必须填写")
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LineContractError("occurred_at 必须是 ISO 时间") from exc
    return raw


def _clean_refs(value: object, field: str) -> list[str]:
    refs = [_text(item) for item in _list(value) if _text(item)]
    if not refs:
        raise LineContractError(f"{field} 至少需要一个引用")
    return list(dict.fromkeys(refs))


def _common(record: Mapping[str, Any], line: str) -> dict[str, Any]:
    contract = LINE_CONTRACTS[line]
    missing = [field for field in contract["required"] if record.get(field) in (None, "", [])]
    if missing:
        raise LineContractError(f"{contract['label']}缺少：{'、'.join(missing)}")
    project_id = _text(record.get("project_id"))
    event_id = _text(record.get("event_id"))
    if not project_id or not event_id:
        raise LineContractError("project_id 和 event_id 不能为空")
    status = _text(record.get("status")).upper()
    if not status:
        raise LineContractError("status 不能为空")
    return {
        "record_id": _text(record.get("record_id")),
        "project_id": project_id,
        "event_id": event_id,
        "occurred_at": _stamp(record.get("occurred_at")),
        "actor": _text(record.get("actor")),
        "status": status,
        "evidence_refs": _clean_refs(record.get("evidence_refs"), "evidence_refs"),
        "basis_refs": _clean_refs(record.get("basis_refs"), "basis_refs") if line == "cost" else [],
        "contract_version": CONTRACT_VERSION,
        "confirmation_status": "PENDING_CONFIRMATION",
        "responsibility": line_responsibility(line),
    }


def normalize_line_record(line: str, record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one line record without persisting it."""
    line = _text(line).lower()
    if line not in LINE_IDS:
        raise LineContractError(f"不支持的业务线：{line}")
    if not isinstance(record, Mapping):
        raise LineContractError("业务线记录必须是对象")
    result = _common(record, line)
    if line == "production":
        progress = _number(record.get("progress"), "progress")
        if progress is None or progress > 100:
            raise LineContractError("progress 必须在 0 到 100 之间")
        result.update({
            "progress": progress,
            "quantity": _number(record.get("quantity"), "quantity"),
            "unit": _text(record.get("unit")),
            "location": dict(record.get("location") or {}) if isinstance(record.get("location"), Mapping) else {},
            "method": _text(record.get("method")),
            "workforce": _text(record.get("workforce")),
            "machinery": _text(record.get("machinery")),
            "materials": _text(record.get("materials")),
            "actual_start": _text(record.get("actual_start")),
            "actual_finish": _text(record.get("actual_finish")),
        })
    elif line == "technical":
        result.update({
            "assessment": _text(record.get("assessment")),
            "drawing_refs": [_text(item) for item in _list(record.get("drawing_refs")) if _text(item)],
            "spec_refs": [_text(item) for item in _list(record.get("spec_refs")) if _text(item)],
            "option_id": _text(record.get("option_id")),
            "feasible": bool(record.get("feasible", False)),
            "safety_pass": bool(record.get("safety_pass", False)),
            "quality_pass": bool(record.get("quality_pass", False)),
            "compliance_pass": bool(record.get("compliance_pass", False)),
            "recommendation": _text(record.get("recommendation")),
        })
        if not result["assessment"]:
            raise LineContractError("技术线 assessment 不能为空")
    else:
        result.update({
            "boq_refs": [_text(item) for item in _list(record.get("boq_refs")) if _text(item)],
            "quantity": _number(record.get("quantity"), "quantity"),
            "unit": _text(record.get("unit")),
            "unit_price": _number(record.get("unit_price"), "unit_price"),
            "amount": _number(record.get("amount"), "amount"),
            "baseline_amount": _number(record.get("baseline_amount"), "baseline_amount"),
            "forecast_amount": _number(record.get("forecast_amount"), "forecast_amount"),
            "expected_profit": _number(record.get("expected_profit"), "expected_profit", non_negative=False),
            "claim_status": _text(record.get("claim_status")).upper() or "NOT_CREATED",
            "recommendation": _text(record.get("recommendation")),
        })
        if not result["boq_refs"] and not result["basis_refs"]:
            raise LineContractError("造价线至少需要清单引用或计价依据引用")
    return result


def preview_line_records(line: str, project_id: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a deterministic preview; preview never mutates project state."""
    if not _text(project_id):
        raise LineContractError("project_id 不能为空")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)) or not records:
        raise LineContractError("records 至少需要一条记录")
    normalized_line = _text(line).lower()
    if normalized_line not in LINE_IDS:
        raise LineContractError(f"不支持的业务线：{normalized_line}")
    normalized = []
    for record in records:
        candidate = dict(record)
        candidate["project_id"] = project_id
        normalized.append(normalize_line_record(normalized_line, candidate))
    return {
        "line": normalized_line,
        "label": LINE_LABELS[normalized_line],
        "contract_version": CONTRACT_VERSION,
        "status": "PENDING_CONFIRMATION",
        "record_count": len(normalized),
        "records": normalized,
        "mapping_targets": list(LINE_CONTRACTS[normalized_line]["maps_to"]),
        "human_confirmation_required": True,
        "confirmation_prompt": LINE_CONTRACTS[normalized_line]["human_confirmation"],
        "responsibility": line_responsibility(normalized_line),
        "decision_boundary": "数据只提供依据；GO/OPTIMIZE/HOLD/REJECT 必须由人确认并留痕。",
    }


def confirm_line_records(preview: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    """Seal a preview with the current human actor; no system actor is accepted."""
    if not isinstance(preview, Mapping) or not preview.get("records"):
        raise LineContractError("请先生成有效的业务线预览")
    line = _text(preview.get("line")).lower()
    policy = line_responsibility(line)
    if not can_confirm_line(line, actor):
        raise PermissionError(f"{policy['head_label']}（{policy['head_role']}）才能确认或修改{LINE_LABELS[line]}责任线")
    username = _text(actor.get("username") or actor.get("id")) if isinstance(actor, Mapping) else ""
    if not username:
        raise LineContractError("人工确认必须有登录人员")
    stamp = datetime.now(timezone.utc).isoformat()
    confirmed = deepcopy(dict(preview))
    confirmed["status"] = "CONFIRMED"
    confirmed["confirmed_by"] = username
    confirmed["confirmed_at"] = stamp
    confirmed["responsibility"] = {
        **policy,
        "assigned_to": username,
        "assigned_at": stamp,
    }
    for record in confirmed["records"]:
        record["confirmation_status"] = "CONFIRMED"
        record["confirmed_by"] = username
        record["confirmed_at"] = stamp
        record["responsibility"] = dict(confirmed["responsibility"])
    return confirmed


def mapping_for_confirmed_record(line: str, record: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    """Map one confirmed record onto existing Core/P01-P08/Outcome paths."""
    if _text(record.get("confirmation_status")) != "CONFIRMED":
        raise LineContractError("未完成人工确认的记录不能映射到 Core")
    line = _text(line).lower()
    if line not in LINE_IDS:
        raise LineContractError(f"不支持的业务线：{line}")
    responsibility = record.get("responsibility") if isinstance(record.get("responsibility"), Mapping) else line_responsibility(line)
    confirmed_by = _text(record.get("confirmed_by") or responsibility.get("assigned_to") or actor.get("username"))
    common = {"record_id": _text(record.get("record_id")), "occurred_at": _text(record.get("occurred_at")), "actor": _text(record.get("actor")), "evidence_refs": list(record.get("evidence_refs") or []), "confirmed_by": confirmed_by}
    if line == "production":
        target = {"production_track": {"status": _text(record.get("status")), "progress": record.get("progress"), "owner": confirmed_by, "actual": {"quantity": record.get("quantity"), "unit": record.get("unit"), "location": dict(record.get("location") or {}), "method": record.get("method"), "workforce": record.get("workforce"), "machinery": record.get("machinery"), "materials": record.get("materials"), "start": record.get("actual_start"), "finish": record.get("actual_finish")}, "records": [common]}}
    elif line == "technical":
        option = {"option_id": record.get("option_id"), "feasible": record.get("feasible"), "safety_pass": record.get("safety_pass"), "quality_pass": record.get("quality_pass"), "compliance_pass": record.get("compliance_pass"), "assessment": record.get("assessment"), "recommendation": record.get("recommendation")}
        target = {"technical_track": {"status": _text(record.get("status")), "owner": confirmed_by, "assessment": record.get("assessment"), "drawing_refs": list(record.get("drawing_refs") or []), "spec_refs": list(record.get("spec_refs") or []), "needed": True, "options": [option]}}
    else:
        evaluation = {"record_id": record.get("record_id"), "boq_refs": list(record.get("boq_refs") or []), "basis_refs": list(record.get("basis_refs") or []), "quantity": record.get("quantity"), "unit": record.get("unit"), "unit_price": record.get("unit_price"), "amount": record.get("amount"), "baseline_amount": record.get("baseline_amount"), "forecast_amount": record.get("forecast_amount"), "expected_profit": record.get("expected_profit"), "recommendation": record.get("recommendation"), "confirmed_by": common["confirmed_by"]}
        target = {"commercial_track": {"status": _text(record.get("status")), "evaluations": [evaluation], "claim_status": _text(record.get("claim_status"))}}
    return {"line": line, "event_id": _text(record.get("event_id")), "record_id": _text(record.get("record_id")), "confirmed": True, "mapped_at": datetime.now(timezone.utc).isoformat(), "responsibility": dict(responsibility), "targets": target, "source_refs": list(record.get("evidence_refs") or []) + list(record.get("basis_refs") or [])}
