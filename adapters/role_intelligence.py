"""Role data-flow contracts and deterministic cross-line alerts.

This adapter is deliberately small and auditable.  It does not invent a new
ledger and it does not let a model guess missing quantities.  It matches the
existing role work products, P01-P08 projections and Core Events by stable
keys, then emits a role-scoped alert when a red-line rule is evidenced.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any, Mapping, Sequence


ROLE_INTELLIGENCE_VERSION = "1.0"

ROLE_DEPARTMENT_HEADS: dict[str, dict[str, str]] = {
    "project_manager": {"department": "项目管理", "head_role": "project_manager", "head_label": "项目经理"},
    "cost_manager": {"department": "造价线", "head_role": "cost_manager", "head_label": "造价经理"},
    "cost_estimator": {"department": "造价线", "head_role": "cost_manager", "head_label": "造价经理"},
    "technical_lead": {"department": "技术线", "head_role": "technical_lead", "head_label": "技术负责人"},
    "production_manager": {"department": "生产线", "head_role": "production_manager", "head_label": "生产经理"},
    "site_engineer": {"department": "生产线", "head_role": "production_manager", "head_label": "生产经理"},
    "surveyor": {"department": "生产线", "head_role": "production_manager", "head_label": "生产经理"},
    "quality_officer": {"department": "技术/质量", "head_role": "technical_lead", "head_label": "技术负责人"},
    "lab_testing_officer": {"department": "技术/试验", "head_role": "technical_lead", "head_label": "技术负责人"},
    "document_controller": {"department": "资料管理", "head_role": "project_manager", "head_label": "项目经理"},
    "safety_officer": {"department": "生产/安全", "head_role": "production_manager", "head_label": "生产经理"},
    "procurement_officer": {"department": "采购线", "head_role": "cost_manager", "head_label": "造价经理"},
    "warehouse_officer": {"department": "物资线", "head_role": "production_manager", "head_label": "生产经理"},
    "administrative_officer": {"department": "行政协同", "head_role": "project_manager", "head_label": "项目经理"},
}


# These are the only cross-line streams the matcher is allowed to read for a
# role.  The list is also returned to the UI so every role can see why an
# alert arrived and where its data is allowed to go next.
ROLE_DATA_STREAMS: dict[str, dict[str, Any]] = {
    "project_manager": {"inputs": ("technical_release", "production_progress", "cost_review", "outcome_queue"), "checks": ("escalation_not_closed", "decision_without_basis")},
    "cost_manager": {"inputs": ("material_baseline", "quantity_measurement", "technical_release", "quality_acceptance", "role_evidence"), "checks": ("amount_without_basis", "quantity_without_evidence", "review_pending")},
    "cost_estimator": {"inputs": ("material_baseline", "site_claim", "survey_result", "quality_acceptance", "role_evidence"), "checks": ("missing_event", "missing_evidence", "quantity_conflict")},
    "technical_lead": {"inputs": ("drawings", "site_event", "production_plan", "quality_acceptance", "lab_test"), "checks": ("release_without_version", "production_before_release", "test_quality_conflict")},
    "production_manager": {"inputs": ("technical_release", "production_plan", "site_fact", "survey_result", "quality_acceptance", "material_inventory"), "checks": ("production_before_release", "progress_without_measurement", "resource_or_material_gap")},
    "site_engineer": {"inputs": ("production_plan", "technical_release", "site_event", "survey_result", "quality_acceptance", "cost_claim"), "checks": ("missing_event", "missing_evidence", "quantity_conflict", "quality_return")},
    "surveyor": {"inputs": ("site_claim", "drawings", "technical_release", "survey_result", "quality_acceptance", "cost_claim"), "checks": ("missing_event", "quantity_conflict", "measurement_without_control" )},
    "quality_officer": {"inputs": ("site_fact", "survey_result", "lab_test", "technical_release"), "checks": ("lab_quality_conflict", "missing_batch_or_location", "reinspection_pending")},
    "lab_testing_officer": {"inputs": ("procurement_order", "warehouse_receipt", "material_baseline", "quality_acceptance"), "checks": ("test_batch_unmatched", "failed_test_in_use", "missing_sample" )},
    "document_controller": {"inputs": ("role_work_products", "evidence", "signoff", "version_history"), "checks": ("incomplete_package", "version_gap", "missing_signoff")},
    "safety_officer": {"inputs": ("production_plan", "technical_release", "site_fact", "corrective_action"), "checks": ("hazard_overdue", "hazard_without_owner", "unclosed_hazard")},
    "procurement_officer": {"inputs": ("material_baseline", "production_plan", "warehouse_receipt", "lab_test"), "checks": ("purchase_over_redline", "receipt_shortage", "test_batch_unmatched", "price_basis_missing")},
    "warehouse_officer": {"inputs": ("material_baseline", "procurement_order", "warehouse_receipt", "site_issue", "lab_test"), "checks": ("quantity_over_redline", "inventory_negative", "surplus_over_redline", "test_batch_unmatched", "exception_pending")},
    "administrative_officer": {"inputs": ("personnel_registry", "authorization", "handover"), "checks": ("authorization_missing", "role_assignment_gap")},
}


REDLINE_RULES = {
    "quantity_rate": "10%",
    "measurement_rate": "5%",
    "negative_inventory": "0",
    "human_confirmation": True,
}


def role_intelligence_contracts(workbench: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return fixed department ownership and allowed cross-line streams."""
    roles = (workbench or {}).get("roles") if isinstance(workbench, Mapping) else {}
    result: dict[str, Any] = {}
    for role, head in ROLE_DEPARTMENT_HEADS.items():
        contract = roles.get(role, {}) if isinstance(roles, Mapping) else {}
        collaboration = contract.get("collaboration", {}) if isinstance(contract, Mapping) else {}
        stream = ROLE_DATA_STREAMS.get(role, {})
        result[role] = {
            "role": role,
            **head,
            "receives_from": list(collaboration.get("receives_from") or []),
            "hands_to": list(collaboration.get("hands_to") or []),
            "escalates_to": list(collaboration.get("escalates_to") or []),
            "inputs": list(stream.get("inputs") or []),
            "checks": list(stream.get("checks") or []),
            "matching": "稳定键优先：Project / Event / WBS / Location / MaterialBatch；缺键只报数据不足，不猜测补齐。",
        }
    return result


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _fields(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("fields")
    return value if isinstance(value, Mapping) else {}


def _links(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("links")
    return value if isinstance(value, Mapping) else {}


def _key(record: Mapping[str, Any], *names: str) -> str:
    fields = _fields(record)
    links = _links(record)
    for name in names:
        value = fields.get(name)
        if value in (None, ""):
            value = links.get(name)
        if value not in (None, ""):
            return _text(value).lower()
    return ""


def _overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left == right or left in right or right in left


def _records(state: Mapping[str, Any], role: str | None = None) -> list[dict[str, Any]]:
    result = []
    for item in state.get("role_work_products") or []:
        if not isinstance(item, Mapping):
            continue
        if role and _text(item.get("role")) != role:
            continue
        result.append(dict(item))
    return result


def _stage_result(state: Mapping[str, Any], stage: str) -> Mapping[str, Any]:
    value = state.get(stage)
    if not isinstance(value, Mapping):
        return {}
    result = value.get("result")
    return result if isinstance(result, Mapping) else value


def _direct_value(record: Mapping[str, Any], *names: str) -> Any:
    fields = _fields(record)
    for name in names:
        value = record.get(name)
        if value in (None, ""):
            value = fields.get(name)
        if value not in (None, ""):
            return value
    return None


def _material_baseline_quantities(state: Mapping[str, Any]) -> dict[str, Decimal]:
    """Read the existing P04/P05/P02 quantity basis, without creating a ledger."""
    # P04 is authoritative; P05/P02 are only fallbacks for projects that have
    # not yet accepted a zero-number ledger.  The matcher never fabricates a
    # quantity when no stable material/item code exists.
    for stage, collection_key in (("baseline", "entries"), ("cost_plan", "items"), ("boq", "items")):
        result = _stage_result(state, stage)
        rows = result.get(collection_key) or []
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            continue
        indexed: dict[str, Decimal] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            code = _text(_direct_value(row, "material_code", "code", "item_code"))
            quantity = _number(_direct_value(row, "quantity", "planned_quantity", "baseline_quantity"))
            if not code or quantity is None or quantity < 0:
                continue
            key = code.lower()
            indexed[key] = indexed.get(key, Decimal("0")) + quantity
        if indexed:
            return indexed
    return {}


def _alert(role: str, code: str, severity: str, title: str, message: str, *, record_ids: Sequence[str] = (), related_roles: Sequence[str] = (), evidence: Sequence[str] = (), target: str = "coordination") -> dict[str, Any]:
    # Python's built-in hash is intentionally randomized between processes.
    # Use a short SHA-1 digest so the same evidence produces the same alert ID
    # after a server restart, which keeps UI acknowledgements and audit links
    # stable without creating a second fact source.
    stable_key = "|".join([role, code, *[str(item) for item in record_ids]])
    stable_id = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:12].upper()
    return {
        "alert_id": f"ROLE-{role}-{code}-{stable_id}",
        "role": role,
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "record_ids": [str(item) for item in record_ids if str(item)],
        "related_roles": [str(item) for item in related_roles if str(item)],
        "evidence": [str(item) for item in evidence if str(item)],
        "view": target,
        "human_confirmation_required": True,
        "derived_only": True,
    }


def _append(alerts: list[dict[str, Any]], seen: set[tuple[str, str, str]], item: dict[str, Any]) -> None:
    key = (item["role"], item["code"], "|".join(item.get("record_ids") or []))
    if key not in seen:
        seen.add(key)
        alerts.append(item)


def derive_role_alerts(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Derive cross-line alerts from existing role products and Core events."""
    selected = set(roles or ROLE_DEPARTMENT_HEADS)
    products = _records(state)
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in products:
        by_role[_text(record.get("role"))].append(record)
    alerts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    # Every role gets a fixed-link check. This exposes incomplete handoffs
    # without changing the record or silently creating a relationship.
    for record in products:
        role = _text(record.get("role"))
        if role not in selected:
            continue
        links = _links(record)
        contract = role_intelligence_contracts({"roles": {role: {"collaboration": {"hands_to": []}}}}).get(role, {})
        event_id = _text(links.get("event_id"))
        evidence = links.get("evidence_refs") or []
        if role not in {"administrative_officer", "project_manager"} and not event_id:
            _append(alerts, seen, _alert(role, "MISSING_EVENT", "warn", "成果未绑定工程事件", "岗位成果没有绑定 Core Event，无法进入固定数据流向。", record_ids=[record.get("product_id", "")], related_roles=contract.get("hands_to", [])))
        if role not in {"administrative_officer", "project_manager"} and not evidence:
            _append(alerts, seen, _alert(role, "MISSING_EVIDENCE", "warn", "成果缺少证据引用", "缺少证据引用，相关岗位只能看到待核对，不能把记录当成已确认事实。", record_ids=[record.get("product_id", "")], related_roles=contract.get("hands_to", [])))

    procurement = by_role["procurement_officer"]
    warehouse = by_role["warehouse_officer"]
    lab = by_role["lab_testing_officer"]
    production = by_role["production_manager"]
    site = by_role["site_engineer"]
    survey = by_role["surveyor"]
    quality = by_role["quality_officer"]
    technical = by_role["technical_lead"]
    baseline_quantities = _material_baseline_quantities(state)

    # Material flow: baseline -> procurement -> receipt/issue -> lab.
    for item in warehouse:
        f = _fields(item)
        record_id = item.get("product_id", "")
        batch = _key(item, "material_batch")
        inventory = _number(f.get("inventory_after"))
        if inventory is not None and inventory < 0:
            _append(alerts, seen, _alert("warehouse_officer", "INVENTORY_NEGATIVE", "block", "库存跌破零线", f"材料批次 {_key(item, 'material_batch') or '未标明'} 的动作后库存为 {inventory}，必须由仓管员和生产/造价负责人确认。", record_ids=[record_id], related_roles=["production_manager", "cost_manager"], target="coordination"))
        if _text(f.get("check_status")).upper() == "EXCEPTION":
            _append(alerts, seen, _alert("warehouse_officer", "WAREHOUSE_EXCEPTION", "warn", "收发存存在异常", "仓管员已标记异常，系统不会自动改写采购或造价事实，应提交固定责任链复核。", record_ids=[record_id], related_roles=["production_manager", "cost_manager"]))
        matching_labs = [row for row in lab if _overlap(batch, _key(row, "material_batch", "sample_id"))]
        if any(_text(_fields(row).get("pass_status")).upper() == "FAIL" for row in matching_labs):
            _append(alerts, seen, _alert("warehouse_officer", "TEST_BATCH_FAIL", "block", "材料试验不合格仍进入收发存链", f"材料批次 {batch or '未标明'} 存在不合格试验结果，入库/发料必须暂停并由技术负责人确认。", record_ids=[record_id], related_roles=["lab_testing_officer", "technical_lead"]))
        if batch and lab and not matching_labs:
            _append(alerts, seen, _alert("warehouse_officer", "TEST_BATCH_UNMATCHED", "warn", "材料批次未匹配试验数据", f"材料批次 {batch} 没有匹配的试验报告，系统只提示待核对，不判定为合格。", record_ids=[record_id], related_roles=["lab_testing_officer", "technical_lead"]))

        baseline_qty = next((quantity for code, quantity in baseline_quantities.items() if _overlap(batch, code)), None)
        if baseline_qty is not None and baseline_qty > 0 and inventory is not None and inventory > baseline_qty * Decimal("1.10"):
            _append(alerts, seen, _alert("warehouse_officer", "SURPLUS_OVER_REDLINE", "warn", "材料节余超过基准红线", f"材料批次 {batch or '未标明'} 当前库存 {inventory}，高于既有基准量 {baseline_qty} 的 110%，需要仓管员、生产经理和造价线核对。", record_ids=[record_id], related_roles=["production_manager", "cost_manager"], evidence=[f"material_baseline:{batch}"]))

        if baseline_qty is not None and baseline_qty > 0 and _text(f.get("movement_type")).upper() == "ISSUE":
            issued = sum((_number(_fields(row).get("quantity")) or Decimal("0")) for row in warehouse if _text(_fields(row).get("movement_type")).upper() == "ISSUE" and _overlap(batch, _key(row, "material_batch")))
            if issued > baseline_qty * Decimal("1.10"):
                _append(alerts, seen, _alert("warehouse_officer", "QUANTITY_OVER_REDLINE", "block", "材料领用超过基准红线", f"材料批次 {batch or '未标明'} 累计领用 {issued}，超过既有基准量 {baseline_qty} 的 110%，不得自动放行。", record_ids=[record_id], related_roles=["production_manager", "cost_manager"], evidence=[f"material_baseline:{batch}"]))

    for item in procurement:
        f = _fields(item)
        code = _key(item, "material_code", "material_batch")
        requested = _number(f.get("requested_qty"))
        receipts = Decimal("0")
        receipt_ids: list[str] = []
        for row in warehouse:
            if _text(_fields(row).get("movement_type")).upper() not in {"RECEIPT", "RETURN"}:
                continue
            if _overlap(code, _key(row, "material_batch")):
                receipts += _number(_fields(row).get("quantity")) or Decimal("0")
                receipt_ids.append(str(row.get("product_id", "")))
        record_id = str(item.get("product_id", ""))
        baseline_qty = next((quantity for baseline_code, quantity in baseline_quantities.items() if _overlap(code, baseline_code)), None)
        if baseline_qty is not None and baseline_qty > 0 and requested is not None and requested > baseline_qty * Decimal("1.10"):
            _append(alerts, seen, _alert("procurement_officer", "PURCHASE_BASELINE_OVER_REDLINE", "block", "采购需求超过材料基准红线", f"材料 {code or '未标明'} 的采购需求 {requested}，超过既有基准量 {baseline_qty} 的 110%，必须由造价经理人工确认。", record_ids=[record_id], related_roles=["cost_manager", "project_manager"], evidence=[f"material_baseline:{code}"]))
        if requested is not None and requested > 0 and receipts > requested * Decimal("1.10"):
            _append(alerts, seen, _alert("procurement_officer", "PURCHASE_OVER_REDLINE", "warn", "采购到货超过需求红线", f"材料 {code or '未标明'} 到货 {receipts}，超过采购需求 {requested} 的 110%，需要造价经理确认。", record_ids=[record_id, *receipt_ids], related_roles=["warehouse_officer", "cost_manager"]))
        if requested is not None and requested > 0 and receipts < requested * Decimal("0.90"):
            _append(alerts, seen, _alert("procurement_officer", "RECEIPT_SHORTAGE", "warn", "采购需求尚未形成足量到货", f"材料 {code or '未标明'} 到货 {receipts}，低于需求 {requested} 的 90%，需要生产经理和仓管员核对。", record_ids=[record_id, *receipt_ids], related_roles=["production_manager", "warehouse_officer"]))
        matching_labs = [row for row in lab if _overlap(code, _key(row, "material_batch", "sample_id"))]
        if matching_labs and any(_text(_fields(row).get("pass_status")).upper() == "FAIL" for row in matching_labs):
            _append(alerts, seen, _alert("procurement_officer", "TEST_BATCH_FAIL", "block", "采购材料试验不匹配", f"材料 {code or '未标明'} 对应试验结果不合格，采购到货不得直接转入正常使用流。", record_ids=[record_id, *(str(row.get("product_id", "")) for row in matching_labs)], related_roles=["lab_testing_officer", "technical_lead"]))

    # Production/site/survey flow: technical release -> plan -> site fact ->
    # survey/quality -> cost evidence. Compare only same Event when present.
    for row in site:
        event_id = _text(_links(row).get("event_id"))
        rid = str(row.get("product_id", ""))
        matching_survey = [item for item in survey if event_id and _text(_links(item).get("event_id")) == event_id]
        site_qty = _number(_fields(row).get("progress_qty"))
        survey_qty = next((_number(_fields(item).get("measured_quantity")) for item in matching_survey if _number(_fields(item).get("measured_quantity")) is not None), None)
        if site_qty is not None and survey_qty is not None:
            denominator = max(abs(site_qty), abs(survey_qty), Decimal("1"))
            if abs(site_qty - survey_qty) / denominator > Decimal("0.05"):
                _append(alerts, seen, _alert("site_engineer", "QUANTITY_CONFLICT", "block", "申报量与实测量不一致", f"同一 Event 的现场申报量 {site_qty} 与实测量 {survey_qty} 偏差超过 5%，不得直接进入造价计量。", record_ids=[rid, *(str(item.get("product_id", "")) for item in matching_survey)], related_roles=["surveyor", "cost_estimator", "production_manager"]))
        if event_id and any(_text(_fields(item).get("result")).upper() in {"RETURN", "HOLD"} for item in quality if _text(_links(item).get("event_id")) == event_id):
            _append(alerts, seen, _alert("site_engineer", "QUALITY_RETURN", "block", "现场成果被质量退回", "同一 Event 的质量结果为退回/暂缓，施工成果不能被系统标记为已完成。", record_ids=[rid, event_id], related_roles=["quality_officer", "production_manager"]))

    for row in survey:
        rid = str(row.get("product_id", ""))
        if not _key(row, "control_point"):
            _append(alerts, seen, _alert("surveyor", "MEASUREMENT_WITHOUT_CONTROL", "warn", "实测成果缺少控制点", "测量成果没有控制点/测站引用，不能作为可靠工程量依据。", record_ids=[rid], related_roles=["technical_lead", "cost_estimator"]))

    for row in quality:
        event_id = _text(_links(row).get("event_id"))
        rid = str(row.get("product_id", ""))
        failed_lab = [item for item in lab if event_id and _text(_links(item).get("event_id")) == event_id and _text(_fields(item).get("pass_status")).upper() == "FAIL"]
        result = _text(_fields(row).get("result")).upper()
        if failed_lab and result == "PASS":
            _append(alerts, seen, _alert("quality_officer", "LAB_QUALITY_CONFLICT", "block", "质量结论与试验结果冲突", "同一 Event 的材料试验为不合格，但质量记录为通过，必须人工复核后才能放行。", record_ids=[rid, *(str(item.get("product_id", "")) for item in failed_lab)], related_roles=["lab_testing_officer", "technical_lead"]))

    for row in technical:
        if _text(_fields(row).get("feasible")).upper() in {"RETURN", "HOLD"}:
            event_id = _text(_links(row).get("event_id"))
            active_production = [item for item in production if event_id and _text(_links(item).get("event_id")) == event_id]
            if active_production:
                _append(alerts, seen, _alert("technical_lead", "PRODUCTION_BEFORE_RELEASE", "block", "技术未放行但生产已有成果", "技术负责人记录为退回/暂缓，但生产线已经形成执行成果，必须停止流转并由技术负责人确认。", record_ids=[str(row.get("product_id", "")), *(str(item.get("product_id", "")) for item in active_production)], related_roles=["production_manager", "project_manager"]))

    # Keep the packet role-scoped and stable for the UI/API consumer.
    return [item for item in alerts if item.get("role") in selected]


def role_intelligence_snapshot(state: Mapping[str, Any], roles: Sequence[str] | None = None, workbench: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selected = list(roles or ROLE_DEPARTMENT_HEADS)
    alerts = derive_role_alerts(state, selected)
    contracts = role_intelligence_contracts(workbench)
    counts = {"block": 0, "warn": 0, "info": 0}
    for item in alerts:
        counts[item.get("severity", "info")] = counts.get(item.get("severity", "info"), 0) + 1
    return {
        "version": ROLE_INTELLIGENCE_VERSION,
        "matching_policy": "deterministic_keyed_match",
        "human_confirmation_required": True,
        "redline_rules": dict(REDLINE_RULES),
        "contracts": {role: contracts[role] for role in selected if role in contracts},
        "alerts": alerts,
        "alert_counts": counts,
        "data_is_evidence_not_decision": True,
        "single_source_of_truth": True,
    }
