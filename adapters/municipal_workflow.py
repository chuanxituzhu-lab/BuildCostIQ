"""Single-project municipal construction workflow acceptance runner.

This adapter is the executable distillation of the municipal project outcome
workflow.  It deliberately sits outside Core: Core keeps the frozen Event and
Outcome state machines, while this module composes P01-P09, the three line
contracts and the collaboration projection into one repeatable acceptance
scenario.

The runner is intentionally deterministic in its business data and uses only
sanitised records.  It is not a second database and it does not create a new
capability.  Every amount still comes from P01-P08 and P09 remains a read-only
projection.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from core import (
    Runtime,
    new_event,
    record_outcome_snapshot,
    transition_event,
    transition_outcome,
    validate_event,
)
from plugins import build_default_plugins
from .collaboration import (
    confirm_decision,
    new_decision,
    new_relation,
    new_task,
    update_task,
)
from .line_contracts import (
    confirm_line_records,
    mapping_for_confirmed_record,
    preview_line_records,
)


MUNICIPAL_ROLES = (
    "project_manager",
    "cost_manager",
    "cost_estimator",
    "technical_lead",
    "production_manager",
    "site_engineer",
    "surveyor",
    "quality_officer",
    "lab_testing_officer",
    "document_controller",
    "safety_officer",
    "procurement_officer",
    "warehouse_officer",
)

GOLDEN_SCENARIOS = (
    {
        "scenario_id": "G01",
        "title": "地下管线冲突",
        "source_type": "SITE_DISCOVERY",
        "event_type": "SITE_CONDITION",
        "outcome_type": "PHYSICAL",
        "location": {"zone": "K0+420-K0+510", "axis": "道路中线", "place": "雨污水交叉口"},
    },
    {
        "scenario_id": "G02",
        "title": "土方工程量增加",
        "source_type": "QUANTITY_VARIANCE",
        "event_type": "QUANTITY_VARIANCE",
        "outcome_type": "COMMERCIAL",
        "location": {"zone": "K1+200-K1+680", "axis": "左幅", "place": "路基填挖方段"},
    },
    {
        "scenario_id": "G03",
        "title": "正式设计变更",
        "source_type": "DESIGN_CHANGE",
        "event_type": "DESIGN_CHANGE",
        "outcome_type": "CONTRACTUAL",
        "location": {"zone": "K2+050", "axis": "横断面", "place": "箱涵节点"},
    },
    {
        "scenario_id": "G04",
        "title": "现场签证",
        "source_type": "OWNER_INSTRUCTION",
        "event_type": "CONTRACT_REVIEW",
        "outcome_type": "COMMERCIAL",
        "location": {"zone": "K2+800", "axis": "右幅", "place": "临时交通导改"},
    },
    {
        "scenario_id": "G05",
        "title": "停窝工与工期索赔",
        "source_type": "SCHEDULE_VARIANCE",
        "event_type": "SCHEDULE_VARIANCE",
        "outcome_type": "SCHEDULE",
        "location": {"zone": "全线", "axis": "施工总进度", "place": "连续降雨影响段"},
    },
)


def _actor(username: str, role: str) -> dict[str, str]:
    return {"username": username, "role": role}


def _facts(project_id: str) -> dict[str, Mapping[str, Any]]:
    """Run the eight professional capabilities on one sanitised project."""
    runtime = Runtime(build_default_plugins())
    common = {"project_id": project_id, "source_id": "SRC-MUNI-DEMO"}
    boq_rows = [
        ["项目编码", "项目名称", "项目特征", "计量单位", "工程量"],
        ["040101001001", "沟槽土方开挖", "三类土，机械开挖", "m3", 1000],
        ["040501001001", "混凝土管道铺设", "DN800，砂石基础", "m", 500],
    ]
    p01 = runtime.gateway.execute(
        "P01",
        {
            **common,
            "contract": {
                "contract_no": "SZ-ROAD-2026-001",
                "title": "市政道路及雨污水工程",
                "owner": "演示建设单位",
                "contractor": "演示施工单位",
                "contract_amount": 1850000,
                "tax_mode": "增值税一般计税",
                "start_date": "2026-03-01",
                "end_date": "2026-09-30",
            },
            "obligations": [
                {"id": "OB-001", "name": "提交施工组织设计", "owner": "contractor", "due_date": "2026-03-05"},
                {"id": "OB-002", "name": "完成隐蔽工程验收", "owner": "supervision", "due_date": "2026-09-20"},
            ],
        },
    )
    p02 = runtime.gateway.execute("P02", {**common, "rows": boq_rows})
    p03 = runtime.gateway.execute(
        "P03",
        {
            **common,
            "drawings": [
                {"drawing_no": "SZ-01", "name": "道路总平面图", "discipline": "road", "revision": "A", "status": "approved"},
                {"drawing_no": "PS-03", "name": "雨污水管线纵断面图", "discipline": "drainage", "revision": "B", "status": "approved"},
            ],
        },
    )
    entries = [
        {"entry_id": "BL-001", "code": "040101001001", "name": "沟槽土方开挖", "unit": "m3", "quantity": 1000, "unit_price": 32, "basis": "中标清单"},
        {"entry_id": "BL-002", "code": "040501001001", "name": "混凝土管道铺设", "unit": "m", "quantity": 500, "unit_price": 680, "basis": "中标清单"},
    ]
    p04 = runtime.gateway.execute("P04", {**common, "entries": entries})
    p05 = runtime.gateway.execute(
        "P05",
        {
            **common,
            "items": p02["items"],
            "contract_prices": {"040101001001": 32, "040501001001": 680},
            "market_prices": {"040101001001": 35, "040501001001": 710},
        },
    )
    p06 = runtime.gateway.execute(
        "P06",
        {
            **common,
            "changes": [
                {"change_id": "CH-001", "title": "管线冲突调整", "reason": "现场既有管线与批准图纸冲突", "amount": 42000, "status": "approved", "owner": "project_manager"},
                {"change_id": "CH-002", "title": "降雨停工影响", "reason": "连续降雨导致关键线路停窝工", "amount": 18000, "status": "pending", "owner": "project_manager"},
            ],
        },
    )
    p07 = runtime.gateway.execute(
        "P07",
        {
            **common,
            "links": [
                {"link_id": "EV-001", "target_type": "change", "target_id": "CH-001", "relation": "supports", "verified": True},
                {"link_id": "EV-002", "target_type": "drawing", "target_id": "PS-03", "relation": "supports", "verified": True},
                {"link_id": "EV-003", "target_type": "photo", "target_id": "PHOTO-K0420", "relation": "supports", "verified": True},
            ],
        },
    )
    review_rows = [
        {"code": "040101001001", "name": "沟槽土方开挖", "unit": "m3", "quantity": 1000, "price": 32, "total": 32000},
        {"code": "040501001001", "name": "混凝土管道铺设", "unit": "m", "quantity": 500, "price": 680, "total": 340000},
    ]
    p08 = runtime.gateway.execute(
        "P08",
        {
            **common,
            "rows": review_rows,
            "reference_units": {"040101001001": "m3", "040501001001": "m"},
            "subject_basis": {"tax_mode": "含税", "price_type": "contract", "price_date": "2026-03"},
            "reference_basis": {"tax_mode": "含税", "price_type": "market", "price_date": "2026-03"},
            "expected_divisions": [("0401", "道路工程"), ("0405", "排水工程")],
        },
    )
    return {"P01": p01, "P02": p02, "P03": p03, "P04": p04, "P05": p05, "P06": p06, "P07": p07, "P08": p08}


def _line_adaptations(project_id: str, event_id: str) -> list[dict[str, Any]]:
    line_actors = {
        "production": _actor("demo-production-manager", "production_manager"),
        "technical": _actor("demo-technical-lead", "technical_lead"),
        "cost": _actor("demo-cost-manager", "cost_manager"),
    }
    records = {
        "production": [{
            "record_id": "PROD-001", "event_id": event_id, "occurred_at": "2026-06-12T09:00:00+00:00",
            "actor": "site-engineer-01", "status": "COMPLETED", "progress": 100,
            "quantity": 500, "unit": "m", "location": {"zone": "K0+420-K0+510", "axis": "道路中线"},
            "method": "沟槽开挖后铺管回填", "workforce": "12人", "machinery": "挖掘机2台",
            "materials": "DN800混凝土管", "evidence_refs": ["PHOTO-K0420", "MEASURE-001"],
        }],
        "technical": [{
            "record_id": "TECH-001", "event_id": event_id, "occurred_at": "2026-06-12T10:00:00+00:00",
            "actor": "technical-lead-01", "status": "APPROVED", "assessment": "调整管线标高并避让既有管线，满足规范和安全要求",
            "drawing_refs": ["PS-03"], "spec_refs": ["SPEC-DRAIN-08"], "option_id": "OPT-001",
            "feasible": True, "safety_pass": True, "quality_pass": True, "compliance_pass": True,
            "recommendation": "GO", "evidence_refs": ["PS-03", "TECH-MEMO-001"],
        }],
        "cost": [{
            "record_id": "COST-001", "event_id": event_id, "occurred_at": "2026-06-12T11:00:00+00:00",
            "actor": "cost-manager-01", "status": "APPROVED", "boq_refs": ["040501001001"],
            "quantity": 62, "unit": "m", "unit_price": 680, "amount": 42160,
            "baseline_amount": 0, "forecast_amount": 42160, "expected_profit": 8200,
            "claim_status": "APPROVED", "recommendation": "GO", "basis_refs": ["CONTRACT-SZ-ROAD-2026-001", "P04:BL-002"],
            "evidence_refs": ["CH-001", "MEASURE-001", "TECH-MEMO-001"],
        }],
    }
    confirmed: list[dict[str, Any]] = []
    for line, payload in records.items():
        preview = preview_line_records(line, project_id, payload)
        actor = line_actors[line]
        sealed = confirm_line_records(preview, actor)
        for record in sealed["records"]:
            confirmed.append({"preview": preview, "confirmation": sealed, "mapping": mapping_for_confirmed_record(line, record, actor)})
    return confirmed


def _event_template(project_id: str, event_id: str, scenario: Mapping[str, str], source_refs: list[str]) -> dict[str, Any]:
    event = new_event(
        project_id,
        event_id=event_id,
        title=str(scenario["title"]),
        summary=f"{scenario['title']}已形成可核验的市政项目成果闭环",
        source_type=str(scenario["source_type"]),
        event_type=str(scenario["event_type"]),
        severity="HIGH",
        discovered_by="site-engineer-01",
        discovered_at="2026-05-01T08:00:00+00:00",
        location=dict(scenario["location"]),
        tags=["municipal", "golden-scenario", str(scenario["scenario_id"])],
        dimensions={"cost": True, "revenue": True, "schedule": True, "quality": True, "safety": True},
        source_refs=source_refs,
    )
    event["baseline_impact"] = {
        "contract": {"affected": True, "baseline_id": "P01:SZ-ROAD-2026-001", "clause_refs": ["C-4.2"]},
        "price": {"affected": True, "baseline_id": "P05:CONTRACT", "boq_refs": ["040501001001"]},
        "quantity": {"affected": True, "baseline_id": "P04:BL-002", "original_quantity": 500, "current_estimate": 562, "unit": "m"},
        "cost": {"affected": True, "baseline_id": "P04:BL-002", "baseline_cost": 340000, "forecast_cost": 382160},
    }
    event["production_track"].update({
        "owner": "production-manager-01", "status": "COMPLETED", "progress": 100,
        "actual": {"start": "2026-05-10", "finish": "2026-06-12", "method": "批准方案施工", "workforce": "12人", "machinery": "挖掘机2台", "materials": "管材、砂石", "quantity": 562, "location": dict(scenario["location"])},
        "records": [{"record_id": "MEASURE-001", "quantity": 562, "unit": "m", "source_refs": source_refs, "confirmed_by": "production-manager-01"}],
    })
    event["technical_track"].update({
        "owner": "technical-lead-01", "status": "APPROVED", "assessment": "方案通过技术、安全、质量和合规检查",
        "needed": True, "drawing_refs": ["PS-03"], "spec_refs": ["SPEC-DRAIN-08"],
        "options": [{"option_id": "OPT-001", "feasible": True, "safety_pass": True, "quality_pass": True, "compliance_pass": True}],
    })
    event["commercial_track"].update({
        "owner": "cost-manager-01", "status": "APPROVED", "evaluations": [{"evaluation_id": "EVAL-001", "amount": 42160, "basis_refs": ["P05:CONTRACT", "P04:BL-002"], "confirmed_by": "cost-manager-01"}],
        "claim_status": "APPROVED",
    })
    event["decision"] = {"status": "CONFIRMED", "type": "GO", "selected_option_id": "OPT-001", "result": "按批准方案执行并形成可申报成果", "reason": "三线资料、合同依据和证据均已具备", "approvals": ["project-manager-01", "cost-manager-01"]}
    event["evidence"] = {
        "items": [{"evidence_id": ref, "source_ref": ref, "verified": True} for ref in source_refs],
        "claims": [{"claim_id": "CLAIM-001", "status": "CONFIRMED", "source_refs": source_refs}],
        "three_evidence": {"technical": "PASS", "production": "PASS", "commercial": "PASS", "status": "PASS", "completeness": 100},
    }
    event["settlement"].update({"measurement_status": "APPROVED", "settlement_submitted": True, "estimated_revenue": 42160, "submitted_amount": 42160, "approved_measurement": 42160, "audit_1": "PASS", "audit_2": "PASS", "final_certified": 42160})
    event["audit_cash"] = {"audit_readiness": 100, "cash_status": "COLLECTED", "cash_collected": 42160}
    event["governance"].update({"responsibility": {"production": "production-manager-01", "technical": "technical-lead-01", "cost": "cost-manager-01", "project_manager": "project-manager-01"}, "external_approval": {"status": "APPROVED", "approved_at": "2026-05-03T09:00:00+00:00"}, "formal_basis": "变更令-2026-001"})
    return event


def _complete_event(event: Mapping[str, Any]) -> dict[str, Any]:
    current = deepcopy(dict(event))
    for target in ("ASSESSED", "PLANNING", "COMMERCIAL_REVIEW", "DECIDED", "APPROVAL", "EXECUTING", "VERIFIED", "CLAIMING", "SETTLEMENT", "AUDITING", "COLLECTION", "CLOSED"):
        current = transition_event(current, target, actor=_actor("project-manager-01", "project_manager"))
    current = record_outcome_snapshot(
        current,
        {"title": current["identity"]["title"], "owner": "project-manager-01", "types": ["PHYSICAL", "COMMERCIAL", "CONTRACTUAL", "SCHEDULE", "CASH"], "contractual_status": "APPROVED", "values": {"physical": 100, "evidence_ready": 100, "submitted": 100, "confirmed": 100, "revenue": 100, "settled": 100, "paid": 100}},
        actor=_actor("cost-manager-01", "cost_manager"),
        reason="三线确认后形成成果价值快照",
    )
    for target in ("PHYSICAL_FORMED", "EVIDENCE_READY", "SUBMITTED", "CONFIRMED", "REVENUE_RECOGNIZED", "SETTLED", "CASH_REALIZED"):
        current = transition_outcome(current, target, actor=_actor("project-manager-01", "project_manager"))
    validate_event(current)
    return current


def _coordination(project_id: str, event_id: str) -> dict[str, Any]:
    pm = _actor("project-manager-01", "project_manager")
    task = new_task(project_id, {"title": "完成管线冲突成果闭环", "description": "收集实测、技术确认、造价申报并提交结算", "role": "cost", "assignee": "cost-manager-01", "event_id": event_id, "target_path": "P08.review → Outcome", "due_at": "2026-06-20", "basis_refs": ["CH-001", "MEASURE-001"]}, pm)
    task.update({"required_inputs": ["P01.contract", "P03.drawings", "P04.baseline", "P07.evidence"], "expected_outputs": ["P08.review", "Outcome.confirmed"], "sla": {"hours": 48, "escalate_to": "project_manager"}, "reviewer": "cost-manager-01", "completion_criteria": ["三证互证通过", "结算资料可审", "Outcome 已确认"]})
    task = update_task(task, "IN_REVIEW", pm, "生产、技术、造价资料已汇总")
    task = update_task(task, "APPROVED", pm, "项目经理确认进入结算")
    task = update_task(task, "CLOSED", pm, "结算审定并回款完成")
    decision = new_decision(project_id, {"event_id": event_id, "decision_type": "GO", "reason": "三线资料、证据和合同依据一致", "option_id": "OPT-001", "basis_refs": ["P01:SZ-ROAD-2026-001", "P07:EV-001"]}, pm)
    decision = confirm_decision(decision, pm)
    relations = [
        new_relation(project_id, {"relation_type": "EVENT_TO_TASK", "from_type": "event", "from_id": event_id, "to_type": "task", "to_id": task["task_id"], "label": "执行动作", "basis_refs": ["CH-001"]}, pm),
        new_relation(project_id, {"relation_type": "EVENT_TO_OUTCOME", "from_type": "event", "from_id": event_id, "to_type": "outcome", "to_id": f"OUT-{event_id}", "label": "成果转化", "basis_refs": ["P08:review"]}, pm),
    ]
    return {"task": task, "decision": decision, "relations": relations}


def _work_products(project_id: str, event: Mapping[str, Any], coordination: Mapping[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    quantity_chain = {"planned": 500, "executed": 562, "measured": 562, "accepted": 562, "commercially_recognized": 562, "approved": 562, "paid": 562}
    material_chain = {"budget": 1200, "purchased": 1180, "delivered": 1180, "warehouse_received": 1180, "issued": 1150, "returned": 20, "consumed": 1130, "theoretical": 1125, "remaining": 5}
    work_product_payload = {
        "project_id": project_id, "event_id": event_id, "action_id": coordination["task"]["task_id"],
        "work_product_id": f"WP-{event_id}", "kind": "municipal-change-closure", "owner": "cost-manager-01",
        "input_refs": ["P01:SZ-ROAD-2026-001", "P03:PS-03", "P04:BL-002", "P07:EV-001"],
        "output_refs": ["P08:review", f"OUT-{event_id}"], "status": "COMPLETED",
        "review": {"executing_role": "site_engineer", "professional_lead": "technical_lead", "final_reviewer": "cost_manager", "work_product_verification": "PASS", "physical_acceptance": "PASS", "commercial_acceptance": "PASS", "returned_to_source_count": 0},
        "quantity_chain": quantity_chain, "material_chain": material_chain,
        "external_candidates": [{"source": "CAD/BIM", "candidate_id": "CAD-001", "status": "HUMAN_CONFIRMED", "confirmed_by": "technical-lead-01"}, {"source": "spreadsheet", "candidate_id": "XLS-001", "status": "HUMAN_CONFIRMED", "confirmed_by": "cost-manager-01"}],
    }
    asset_bytes = json.dumps(work_product_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digital_asset = {"asset_id": f"ASSET-{event_id}", "kind": "project-exchange-package", "immutable": True, "content_hash": hashlib.sha256(asset_bytes).hexdigest(), "source_refs": work_product_payload["output_refs"], "created_by": "document-controller-01"}
    alert = {"alert_id": f"ALERT-{event_id}", "type": "EVIDENCE", "severity": "INFO", "status": "CLOSED", "message": "三证互证完成", "corrective_action": "完成 P07 证据核验并由造价经理确认", "escalation": ["cost_manager", "project_manager"], "basis_refs": ["P07:EV-001"]}
    return {"action": coordination["task"], "work_product": work_product_payload, "digital_asset": digital_asset, "alerts": [alert], "role_workbenches": {role: {"owner": role, "isolated": True, "can_edit": [role]} for role in MUNICIPAL_ROLES}}


def run_municipal_workflow(project_id: str = "municipal-road-demo-2026") -> dict[str, Any]:
    """Run and verify one complete municipal project with five golden events."""
    facts = _facts(project_id)
    primary_id = "EV-2026-0001"
    source_refs = ["SRC-MUNI-DEMO:CONTRACT", "SRC-MUNI-DEMO:PS-03", "SRC-MUNI-DEMO:PHOTO-K0420", "SRC-MUNI-DEMO:MEASURE-001"]
    events = [_complete_event(_event_template(project_id, f"EV-2026-000{i + 1}", scenario, source_refs)) for i, scenario in enumerate(GOLDEN_SCENARIOS)]
    line_adaptations = _line_adaptations(project_id, primary_id)
    coordination = _coordination(project_id, primary_id)
    primary_event = next(event for event in events if event["event_id"] == primary_id)
    work_products = _work_products(project_id, primary_event, coordination)
    runtime = Runtime(build_default_plugins())
    p09 = runtime.gateway.execute("P09", {"project_id": project_id, "events": events, "facts": facts})
    checks = {
        "capabilities_p01_p09": runtime.gateway.registered == tuple(f"P{i:02d}" for i in range(1, 10)),
        "all_facts_accepted": all(facts[key].get("status") == "accepted" for key in facts),
        "p08_publishable": bool(facts["P08"].get("publishable")),
        "five_golden_scenarios": len(events) == 5 and {event["identity"]["title"] for event in events} == {item["title"] for item in GOLDEN_SCENARIOS},
        "event_lifecycle_closed": all(event["status"] == "CLOSED" for event in events),
        "outcome_lifecycle_cash_realized": all(event["outcome_track"]["status"] == "CASH_REALIZED" for event in events),
        "line_human_confirmed": bool(line_adaptations) and all(item["confirmation"]["status"] == "CONFIRMED" and item["mapping"]["confirmed"] for item in line_adaptations),
        "collaboration_closed_and_confirmed": coordination["task"]["status"] == "CLOSED" and coordination["decision"]["status"] == "CONFIRMED",
        "three_level_acceptance": all(work_products["work_product"]["review"][key] == "PASS" for key in ("work_product_verification", "physical_acceptance", "commercial_acceptance")),
        "quantity_chain_complete": tuple(work_products["work_product"]["quantity_chain"]) == ("planned", "executed", "measured", "accepted", "commercially_recognized", "approved", "paid"),
        "material_chain_complete": tuple(work_products["work_product"]["material_chain"]) == ("budget", "purchased", "delivered", "warehouse_received", "issued", "returned", "consumed", "theoretical", "remaining"),
        "external_candidates_human_confirmed": all(item["status"] == "HUMAN_CONFIRMED" for item in work_products["work_product"]["external_candidates"]),
        "p09_no_duplicate_ledger": p09["rules"]["single_fact_source"] and p09["rules"]["derived_values_only"],
        "p09_closed_queue": p09["summary"]["event_count"] == 5 and p09["summary"]["open_event_count"] == 0,
        "digital_asset_hashed": bool(work_products["digital_asset"]["content_hash"]) and work_products["digital_asset"]["immutable"],
    }
    return {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "project": {"id": project_id, "name": "市政道路及雨污水工程（脱敏演示）", "workflow": "Project → Event → Action → WorkProduct → Evidence → Verification → Outcome → Digital Asset"},
        "facts": facts,
        "events": events,
        "line_adaptations": line_adaptations,
        "coordination": coordination,
        "work_products": work_products,
        "p09": p09,
        "checks": checks,
        "manual_gates": ["业务线记录必须由责任人确认", "GO/OPTIMIZE/HOLD/REJECT 必须由人确认", "外部 CAD/BIM/Office 结果只能作为候选数据", "结算发布仍需造价经理确认"],
        "roles": list(MUNICIPAL_ROLES),
        "golden_scenarios": [dict(item) for item in GOLDEN_SCENARIOS],
    }


def persist_municipal_demo(result: Mapping[str, Any], workspace: Any = None) -> dict[str, Any]:
    """Persist a passed acceptance packet into the local project workspace.

    Persistence is opt-in so ordinary tests remain side-effect free.  The
    workspace receives references to the already validated P01-P09 results;
    no synthetic source bytes or second amount ledger is created.
    """
    from .workspace import LocalProjectWorkspace

    if not isinstance(result, Mapping) or result.get("status") != "PASSED":
        raise ValueError("only a PASSED municipal workflow packet can be persisted")
    store = workspace or LocalProjectWorkspace()
    project = result["project"]
    state = store.create(str(project["id"]), str(project["name"]))
    for capability_id, payload in (result.get("facts") or {}).items():
        stage = {"P01": "contract", "P02": "boq", "P03": "drawings", "P04": "baseline", "P05": "cost_plan", "P06": "changes", "P07": "evidence", "P08": "review"}.get(capability_id)
        if stage:
            state = store.set_stage(str(project["id"]), stage, payload)
    state = store.save_event(str(project["id"]), result["events"][0])
    state["events"] = [dict(item) for item in result["events"]]
    state["line_adaptations"] = [dict(item) for item in result["line_adaptations"]]
    state["collaboration"] = {"tasks": [dict(result["coordination"]["task"])], "decisions": [dict(result["coordination"]["decision"])]}
    state["relationships"] = [dict(item) for item in result["coordination"]["relations"]]
    state["golden_scenario"] = {"scenarios": [dict(item) for item in result["golden_scenarios"]], "acceptance": dict(result["checks"]), "work_product": dict(result["work_products"]["work_product"]), "digital_asset": dict(result["work_products"]["digital_asset"])}
    state["audit_log"] = [
        {"action": "municipal.workflow.verified", "target": str(project["id"]), "actor": {"username": "system-acceptance", "role": "audit"}, "details": {"checks": dict(result["checks"])}},
    ]
    return store.save(state)


__all__ = ["GOLDEN_SCENARIOS", "MUNICIPAL_ROLES", "persist_municipal_demo", "run_municipal_workflow"]
