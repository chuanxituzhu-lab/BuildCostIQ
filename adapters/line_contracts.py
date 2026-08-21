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

# The role chain is the operating contract around the three business lines.
# It describes who supplies the next accountable role and what may be changed;
# it does not create a new capability or a second facts/amount ledger.
ROLE_FLOW_VERSION = "1.0"
ROLE_FLOW_CONTRACTS: dict[str, dict[str, Any]] = {
    "project_manager": {
        "label": "项目经理",
        "workflow": ("看异常池", "定责任与优先级", "做 GO/OPTIMIZE/HOLD/REJECT 决策", "验纠偏与价值兑现"),
        "inputs": ("未执行 Action", "未关闭 Alert", "技术/生产/造价升级事项", "Outcome 经营队列"),
        "outputs": ("决策记录", "资源协调", "升级处置", "经营确认"),
        "next_roles": ("technical_lead", "production_manager", "cost_manager"),
        "escalates_to": (),
        "can_change": ("decision", "priority", "resource_coordination", "personnel_assignment"),
        "cannot_change": ("technical_fact", "production_fact", "measured_quantity", "cost_fact"),
        "gate": "项目经理只做决策和协调，不直接改写专业事实；所有决策必须有人确认并留痕。",
    },
    "cost_manager": {
        "label": "造价经理",
        "workflow": ("建立造价基准", "接收技术/生产/证据成果", "商业审核与量价复核", "计量结算与 Outcome 总审"),
        "inputs": ("合同与清单", "P04 零号台账", "技术放行", "已测量/验收数量", "P07 证据"),
        "outputs": ("目标成本", "商业评价", "计量/结算审核", "价值兑现结果"),
        "next_roles": ("project_manager",),
        "escalates_to": ("technical_lead", "production_manager", "project_manager"),
        "can_change": ("P01-P08 commercial facts", "commercial acceptance", "cost review"),
        "cannot_change": ("technical_conclusion", "production_fact", "measurement_fact", "quality_fact"),
        "gate": "造价是价值主线总审；金额必须有来源、口径、证据和人工确认，P09 只读取已有事实。",
    },
    "cost_estimator": {
        "label": "造价员",
        "workflow": ("接收基准", "整理工程量/签证", "关联证据", "提交造价经理总审"),
        "inputs": ("合同/清单", "测量与验收成果", "技术变更", "现场证据"),
        "outputs": ("工程量台账", "计量基础", "成本事实", "签证基础"),
        "next_roles": ("cost_manager",),
        "escalates_to": ("cost_manager",),
        "can_change": ("P02/P04/P05/P06/P07 cost inputs"),
        "cannot_change": ("technical_conclusion", "production_fact", "approved_quantity"),
        "gate": "只维护造价基础，缺依据或口径冲突时退回源岗位，不猜测补齐。",
    },
    "technical_lead": {
        "label": "技术负责人",
        "workflow": ("接收现场问题", "拆分工作包/审方案", "技术交底", "技术放行/验收移交"),
        "inputs": ("图纸版本", "规范/技术条件", "现场 Event", "分包方案"),
        "outputs": ("技术判定", "方案与交底", "技术核定/变更", "技术放行证据"),
        "next_roles": ("production_manager", "quality_officer", "cost_manager"),
        "escalates_to": ("project_manager",),
        "can_change": ("P03 drawings", "technical_track", "technical_gate"),
        "cannot_change": ("cost_fact", "production_fact", "measured_quantity"),
        "gate": "没有图纸版本、方案确认和技术交底，不得进入现场实施；技术结论先过人工闸门。",
    },
    "production_manager": {
        "label": "生产经理",
        "workflow": ("接收技术放行", "排计划/配资源", "跟踪实物量", "纠偏并量验移交"),
        "inputs": ("技术放行", "WBS/计划", "资源条件", "施工/分包现场事实"),
        "outputs": ("生产计划", "资源组织", "进度与实物量", "纠偏/移交记录"),
        "next_roles": ("site_engineer", "surveyor", "quality_officer", "cost_manager"),
        "escalates_to": ("project_manager",),
        "can_change": ("production_plan", "production_track", "resource_coordination", "corrective_action"),
        "cannot_change": ("technical_conclusion", "measured_quantity", "quality_acceptance", "cost_fact"),
        "gate": "没有技术放行、责任人和资源计划不下达；完成量未经测量/质量/造价复核不关闭。",
    },
    "site_engineer": {
        "label": "施工员/测量员",
        "workflow": ("接收生产任务", "记录位置/WBS/时间", "提交执行事实", "等待专业复核"),
        "inputs": ("生产计划", "技术交底", "现场位置与作业条件"),
        "outputs": ("施工事实", "完成量申报", "施工事件", "现场证据"),
        "next_roles": ("surveyor", "quality_officer", "technical_lead", "production_manager"),
        "escalates_to": ("production_manager",),
        "can_change": ("site_fact", "executed_quantity_claim"),
        "cannot_change": ("measured_quantity", "quality_acceptance", "cost_fact"),
        "gate": "事实一次录入并绑定 Project/WBS/Location/Event/Time，错误回源头修订。",
    },
    "surveyor": {
        "label": "测量员",
        "workflow": ("接收实测任务", "核控制点/图纸", "形成实测成果", "提交质量与造价复核"),
        "inputs": ("现场完成量申报", "图纸/控制点", "测量范围"),
        "outputs": ("坐标/标高", "实测工程量", "测量证据"),
        "next_roles": ("quality_officer", "cost_estimator", "technical_lead"),
        "escalates_to": ("technical_lead",),
        "can_change": ("measured_quantity", "survey_evidence"),
        "cannot_change": ("site_fact", "quality_acceptance", "cost_fact"),
        "gate": "测量数据只追加版本，不覆盖原始实测，不以口头数量替代实测。",
    },
    "quality_officer": {
        "label": "质量负责人",
        "workflow": ("接收报验", "工序/实体检查", "整改复验", "形成实体验收"),
        "inputs": ("施工事实", "测量成果", "试验报告", "技术标准"),
        "outputs": ("检查记录", "整改复验", "实体验收结论"),
        "next_roles": ("document_controller", "cost_estimator", "technical_lead"),
        "escalates_to": ("technical_lead", "project_manager"),
        "can_change": ("physical_acceptance", "quality_evidence"),
        "cannot_change": ("technical_conclusion", "measured_quantity", "cost_fact"),
        "gate": "不合格必须退回源岗位，未完成整改和复验不得进入计量证据链。",
    },
    "lab_testing_officer": {
        "label": "试验检测员",
        "workflow": ("核对材料批次", "取样送检", "登记报告", "关联质量/资料/物资"),
        "inputs": ("采购到货", "入库批次", "取样计划", "规范要求"),
        "outputs": ("取样记录", "试验报告", "批次校验"),
        "next_roles": ("quality_officer", "document_controller", "warehouse_officer"),
        "escalates_to": ("technical_lead",),
        "can_change": ("test_result", "material_batch_evidence"),
        "cannot_change": ("procurement_fact", "warehouse_fact", "cost_fact"),
        "gate": "报告必须绑定材料批次和工程位置，缺批次或不合格立即形成异常。",
    },
    "document_controller": {
        "label": "资料员",
        "workflow": ("收成果", "查完整性", "归档版本", "形成数字资产"),
        "inputs": ("各岗位 WorkProduct", "证据与签认", "版本历史"),
        "outputs": ("报验资料", "证据包", "归档台账", "数字资产完整性"),
        "next_roles": ("cost_manager", "project_manager"),
        "escalates_to": ("project_manager",),
        "can_change": ("archive_metadata", "asset_completeness"),
        "cannot_change": ("business_fact", "technical_conclusion", "cost_fact"),
        "gate": "只检查和归档，不补造事实；缺资料退回源岗位。",
    },
    "safety_officer": {
        "label": "安全员",
        "workflow": ("巡检发现", "下发隐患", "跟踪整改", "复查关闭"),
        "inputs": ("生产计划", "技术方案", "现场安全事实"),
        "outputs": ("安全检查", "隐患单", "整改复查", "安全验收"),
        "next_roles": ("production_manager", "technical_lead"),
        "escalates_to": ("project_manager",),
        "can_change": ("safety_finding", "corrective_action"),
        "cannot_change": ("production_fact", "technical_conclusion", "cost_fact"),
        "gate": "隐患必须有责任人、期限和关闭证据。",
    },
    "procurement_officer": {
        "label": "采购员",
        "workflow": ("引用造价基准", "询价比价", "下单跟货", "到货交仓/试验"),
        "inputs": ("P04/P05 造价基准", "生产需求", "供应商与订单"),
        "outputs": ("采购计划", "订单", "到货记录", "价量偏差"),
        "next_roles": ("warehouse_officer", "lab_testing_officer", "cost_manager"),
        "escalates_to": ("cost_manager", "project_manager"),
        "can_change": ("procurement_fact", "supplier_fact"),
        "cannot_change": ("cost_baseline", "warehouse_fact", "test_result"),
        "gate": "采购不改造价基准；超量超价必须提交造价线和项目经理确认。",
    },
    "warehouse_officer": {
        "label": "仓管员",
        "workflow": ("核到货批次", "验收入库", "按单发料", "盘点对账"),
        "inputs": ("采购到货", "验收/试验状态", "领料单", "退料单"),
        "outputs": ("入库", "出库", "退库", "库存/盘点", "超领/节余异常"),
        "next_roles": ("production_manager", "lab_testing_officer", "cost_manager"),
        "escalates_to": ("production_manager", "cost_manager"),
        "can_change": ("warehouse_fact", "inventory_balance"),
        "cannot_change": ("procurement_fact", "cost_baseline", "test_result"),
        "gate": "收发存绑定采购批次和施工领用；异常只上报，不改上游事实。",
    },
    "administrative_officer": {
        "label": "行政人员",
        "workflow": ("接收项目经理授权", "维护项目名册", "记录交接", "回报项目经理"),
        "inputs": ("人员姓名/岗位", "授权记录", "交接信息"),
        "outputs": ("项目人员名册", "授权留痕", "交接记录"),
        "next_roles": ("project_manager",),
        "escalates_to": ("project_manager",),
        "can_change": ("personnel_membership", "handover_record"),
        "cannot_change": ("business_fact", "role_policy", "cost_fact"),
        "gate": "没有项目经理授权不增删人员、不改变岗位权限。",
    },
}


def role_flow_contracts() -> dict[str, Any]:
    """Return a read-only projection of the role handoff contract."""
    return {"version": ROLE_FLOW_VERSION, "roles": deepcopy(ROLE_FLOW_CONTRACTS)}

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
