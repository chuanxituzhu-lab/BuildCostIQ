"""Deterministic event intake and role requirement projections.

Production and technical roles submit their own facts and evidence.  They do
not create Core Events or select an event from a dropdown.  This adapter only
derives candidates and fixed work requirements from existing records; the
cost manager remains the human owner who labels, starts, and confirms an
engineering event.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence


EVENT_INTAKE_VERSION = "1.0"

EVENT_SOURCE_ROLES = {
    "production_manager",
    "technical_lead",
    "site_engineer",
    "surveyor",
    "quality_officer",
    "lab_testing_officer",
    "safety_officer",
    "procurement_officer",
    "warehouse_officer",
}

# These terms are deliberately explicit and reviewable.  They are not a
# language model and never create an event; they only explain why a record was
# placed in the cost manager's intake queue.
EVENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SITE_CONDITION": ("障碍", "地下", "管线", "地质", "现场条件", "积水", "塌方", "冲突", "障碍物"),
    "DESIGN_CHANGE": ("设计变更", "变更图", "图纸变更", "设计调整", "洽商", "核定"),
    "CONTRACT_REVIEW": ("合同", "清单", "计价", "索赔", "签证", "业主指令"),
    "COST_VARIANCE": ("成本", "超支", "节余", "价格偏差", "金额偏差", "预算"),
    "QUANTITY_VARIANCE": ("工程量", "数量", "实测", "计量", "超领", "少领", "完成量"),
    "SCHEDULE_VARIANCE": ("进度", "工期", "延期", "滞后", "赶工", "计划"),
    "TECH_OPTIMIZATION": ("优化", "方案", "技术", "工艺", "规范", "可行性", "技术交底"),
    "AUDIT_FEEDBACK": ("审计", "整改", "复核", "不合格", "退回", "问题单"),
}

ROLE_EVENT_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "project_manager": {"label": "项目经理决策与资源确认", "due_hours": 24, "deliverables": ("责任与优先级", "GO/OPTIMIZE/HOLD/REJECT 判断", "资源协调或升级记录")},
    "cost_manager": {"label": "造价经理事件标注与发起", "due_hours": 4, "deliverables": ("确认事件分类与严重程度", "标注受影响基线和维度", "组织生产/技术证据与责任链")},
    "technical_lead": {"label": "技术判断与放行依据", "due_hours": 24, "deliverables": ("图纸/规范版本", "技术必要性与方案判断", "技术交底或放行结论")},
    "production_manager": {"label": "生产计划与资源影响", "due_hours": 24, "deliverables": ("工作包与责任人", "计划/资源影响", "进度和纠偏记录")},
    "site_engineer": {"label": "现场日志与照片事实", "due_hours": 24, "deliverables": ("施工日志", "位置/WBS/时间", "现场照片与完成量")},
    "surveyor": {"label": "测量与工程量依据", "due_hours": 48, "deliverables": ("控制点/测站", "实测坐标标高", "实测工程量")},
    "quality_officer": {"label": "质量检查与复验", "due_hours": 48, "deliverables": ("检验批/工序检查", "缺陷整改要求", "复验或验收结论")},
    "lab_testing_officer": {"label": "材料试验批次证据", "due_hours": 48, "deliverables": ("取样编号", "试验报告", "材料批次合格状态")},
    "document_controller": {"label": "证据包与版本归档", "due_hours": 72, "deliverables": ("资料版本", "来源与签认引用", "归档完整性")},
    "cost_estimator": {"label": "计量与造价基础", "due_hours": 72, "deliverables": ("清单/WBS对应项", "工程量口径", "计价依据与待确认项")},
    "safety_officer": {"label": "安全影响与整改闭环", "due_hours": 24, "deliverables": ("隐患位置", "责任人和期限", "整改复查证据")},
    "procurement_officer": {"label": "采购与到货依据", "due_hours": 48, "deliverables": ("需求/订单", "供应商与到货", "价量偏差说明")},
    "warehouse_officer": {"label": "收发存与材料批次", "due_hours": 48, "deliverables": ("入库/领料单", "材料批次与库存", "异常核对结果")},
}

EVENT_ROLE_ROUTING: dict[str, tuple[str, ...]] = {
    "SITE_CONDITION": ("cost_manager", "technical_lead", "production_manager", "site_engineer", "surveyor", "quality_officer", "document_controller", "cost_estimator"),
    "DESIGN_CHANGE": ("cost_manager", "technical_lead", "production_manager", "site_engineer", "cost_estimator", "document_controller"),
    "CONTRACT_REVIEW": ("cost_manager", "cost_estimator", "document_controller", "project_manager"),
    "COST_VARIANCE": ("cost_manager", "cost_estimator", "production_manager", "procurement_officer", "warehouse_officer", "document_controller"),
    "QUANTITY_VARIANCE": ("cost_manager", "cost_estimator", "production_manager", "site_engineer", "surveyor", "quality_officer", "document_controller"),
    "SCHEDULE_VARIANCE": ("cost_manager", "production_manager", "site_engineer", "technical_lead", "document_controller"),
    "TECH_OPTIMIZATION": ("cost_manager", "technical_lead", "production_manager", "site_engineer", "cost_estimator", "document_controller"),
    "AUDIT_FEEDBACK": ("cost_manager", "project_manager", "technical_lead", "quality_officer", "document_controller"),
}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _fields(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(record.get("fields"))


def _links(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(record.get("links"))


def _event_identity(event: Mapping[str, Any]) -> tuple[str, str, set[str], str]:
    identity = _mapping(event.get("identity"))
    classification = _mapping(event.get("classification"))
    origin = _mapping(event.get("origin"))
    title = _text(identity.get("title"))
    summary = _text(identity.get("summary"))
    tags = {_text(item).lower() for item in classification.get("tags") or [] if _text(item)}
    location = _mapping(origin.get("location"))
    location_key = "|".join(_text(location.get(key)).lower() for key in ("zone", "axis", "level", "place") if _text(location.get(key)))
    return title, summary, tags, location_key


def _record_text(record: Mapping[str, Any]) -> str:
    source_refs = _links(record).get("source_refs") or []
    if isinstance(source_refs, str):
        source_refs = [source_refs]
    values = [record.get("role"), record.get("product_type"), *_fields(record).values(), *source_refs]
    return " ".join(_text(value).lower() for value in values if _text(value))


def _keywords(text: str) -> set[str]:
    return {keyword for terms in EVENT_KEYWORDS.values() for keyword in terms if keyword.lower() in text}


def _location(record: Mapping[str, Any]) -> str:
    fields = _fields(record)
    return "|".join(_text(fields.get(key)).lower() for key in ("location", "zone", "axis", "level", "place") if _text(fields.get(key)))


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _due_at(event: Mapping[str, Any], due_hours: int) -> str:
    origin = _mapping(event.get("origin"))
    base = _parse_time(origin.get("discovered_at"))
    if base is None:
        return ""
    return (base + timedelta(hours=due_hours)).isoformat()


def match_event_candidates(product: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return explainable candidates; never mutate a product or event."""
    text = _record_text(product)
    keys = _keywords(text)
    location = _location(product)
    candidates: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        title, summary, tags, event_location = _event_identity(event)
        event_text = " ".join((title, summary, " ".join(tags))).lower()
        matched_keywords = sorted(keyword for keyword in keys if keyword.lower() in event_text)
        score = len(matched_keywords)
        location_match = bool(location and event_location and (location == event_location or location in event_location or event_location in location))
        if location_match:
            score += 2
        if not matched_keywords and not location_match:
            continue
        if score < 2:
            continue
        candidates.append({
            "event_id": _text(event.get("event_id")),
            "title": title,
            "score": score,
            "matched_keywords": matched_keywords,
            "location_match": location_match,
            "confidence": "HIGH" if score >= 4 or (location_match and matched_keywords) else "MEDIUM",
        })
    return sorted(candidates, key=lambda item: (-int(item["score"]), item["event_id"]))


def derive_event_intake(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> list[dict[str, Any]]:
    selected = set(roles or EVENT_SOURCE_ROLES)
    events = [dict(item) for item in state.get("events") or [] if isinstance(item, Mapping)]
    result: list[dict[str, Any]] = []
    for product in state.get("role_work_products") or []:
        if not isinstance(product, Mapping):
            continue
        role = _text(product.get("role"))
        if role not in selected:
            continue
        links = _links(product)
        linked_event = _text(links.get("event_id"))
        link_state = _text(product.get("event_link_state")).upper()
        if linked_event:
            feedback = _mapping(product.get("event_feedback"))
            review_state = _text(product.get("event_review_state")).upper()
            result.append({
                "intake_id": f"INTAKE-{_text(product.get('product_id'))}",
                "product_id": _text(product.get("product_id")),
                "role": role,
                "role_label": _text(product.get("role_label")) or role,
                "status": "RETURNED" if review_state == "RETURNED" else "LINKED",
                "event_id": linked_event,
                "requires_cost_manager": False,
                "candidates": [],
                "keywords": sorted(_keywords(_record_text(product))),
                "feedback": dict(feedback) if feedback else {},
            })
            continue
        if link_state == "REJECTED":
            result.append({"intake_id": f"INTAKE-{_text(product.get('product_id'))}", "product_id": _text(product.get("product_id")), "role": role, "role_label": _text(product.get("role_label")) or role, "status": "REJECTED", "event_id": "", "requires_cost_manager": False, "candidates": [], "keywords": sorted(_keywords(_record_text(product))), "reason": "造价经理已退回本次事件归类，原始岗位成果仍保留"})
            continue
        candidates = match_event_candidates(product, events)
        result.append({
            "intake_id": f"INTAKE-{_text(product.get('product_id'))}",
            "product_id": _text(product.get("product_id")),
            "role": role,
            "role_label": _text(product.get("role_label")) or role,
            "product_type": _text(product.get("product_type")),
            "status": "SUGGESTED" if candidates else "UNLINKED",
            "event_id": "",
            "requires_cost_manager": True,
            "keywords": sorted(_keywords(_record_text(product))),
            "candidates": candidates[:5],
            "source_refs": list(_links(product).get("source_refs") or []),
            "evidence_refs": list(_links(product).get("evidence_refs") or []),
            "reason": "稳定位置/关键词命中，等待造价经理确认" if candidates else "没有足够稳定键或关键词，等待造价经理标注",
        })
    return result


def _roles_for_event(event: Mapping[str, Any]) -> tuple[str, ...]:
    classification = _mapping(event.get("classification"))
    event_type = _text(classification.get("event_type"))
    return EVENT_ROLE_ROUTING.get(event_type, ("cost_manager", "technical_lead", "production_manager", "site_engineer", "cost_estimator", "document_controller"))


def build_event_requirements(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> list[dict[str, Any]]:
    selected = set(roles or ROLE_EVENT_REQUIREMENTS)
    products = [item for item in state.get("role_work_products") or [] if isinstance(item, Mapping)]
    requirements: list[dict[str, Any]] = []
    for event in state.get("events") or []:
        if not isinstance(event, Mapping) or _text(event.get("status")) in {"CLOSED", "ABANDONED"}:
            continue
        event_id = _text(event.get("event_id"))
        for role in _roles_for_event(event):
            if role not in selected or role not in ROLE_EVENT_REQUIREMENTS:
                continue
            spec = ROLE_EVENT_REQUIREMENTS[role]
            submitted = [item for item in products if _text(item.get("role")) == role and _text(_links(item).get("event_id")) == event_id and _text(item.get("status")).upper() not in {"REJECTED", "CANCELLED"}]
            returned_product = next(
                (item for item in reversed(submitted) if _text(item.get("event_review_state")).upper() == "RETURNED"),
                None,
            )
            feedback = _mapping(returned_product.get("event_feedback")) if isinstance(returned_product, Mapping) else {}
            requirements.append({
                "requirement_id": f"REQ-{event_id}-{role}",
                "event_id": event_id,
                "event_title": _text(_mapping(event.get("identity")).get("title")),
                "event_status": _text(event.get("status")) or "DISCOVERED",
                "role": role,
                "label": spec["label"],
                "deliverables": list(spec["deliverables"]),
                "due_hours": spec["due_hours"],
                "due_at": _due_at(event, int(spec["due_hours"])),
                "status": "RETURNED" if returned_product else ("SUBMITTED" if submitted else "OPEN"),
                "submitted_product_ids": [_text(item.get("product_id")) for item in submitted],
                "feedback": dict(feedback) if feedback else {},
                "human_confirmation_required": True,
                "fixed_assignment": True,
            })
    return requirements


def event_intake_snapshot(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> dict[str, Any]:
    selected = list(roles or ROLE_EVENT_REQUIREMENTS)
    intake = derive_event_intake(state)
    requirements = build_event_requirements(state, selected)
    visible_intake = intake if "cost_manager" in selected else [item for item in intake if item.get("role") in set(selected)]
    return {
        "version": EVENT_INTAKE_VERSION,
        "policy": "production_technical_submit_facts_cost_manager_labels_and_starts_event",
        "event_initiator_role": "cost_manager",
        "intake": visible_intake,
        "requirements": requirements,
        "keyword_matching": "deterministic_local_keywords_and_location_only",
        "auto_create_event": False,
        "auto_decision": False,
        "human_confirmation_required": True,
    }
