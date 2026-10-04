"""Chinese, single-project business workflow contracts and state projection.

This layer records human work and decisions. It never computes or approves
professional conclusions on behalf of a construction project role.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4


class BusinessWorkflowError(ValueError):
    """A workflow action or its persisted evidence is invalid."""


def _field(key: str, label: str, *, required: bool = True, kind: str = "text", help_text: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "required": required, "kind": kind, "help": help_text}


def _step(key: str, label: str, roles: Sequence[str], checks: Sequence[str], kind: str = "review") -> dict[str, Any]:
    return {"key": key, "label": label, "roles": list(roles), "checks": list(checks), "kind": kind}


MODULES: dict[str, dict[str, Any]] = {
    "01": {
        "workflow_id": "WF01", "name": "造价依据（政府行业文件）", "submit_roles": ["cost_manager", "cost_estimator", "document_controller"],
        "fields": [_field("title", "文件名称"), _field("issuer", "发布机关"), _field("document_no", "文件编号"), _field("region", "适用地区"), _field("published_date", "发布日期", kind="date"), _field("effective_date", "生效日期", kind="date"), _field("version", "版本/修订号"), _field("scope", "适用专业或范围")],
        "steps": [_step("source_review", "来源与版本复核", ["cost_manager"], ["原始文件可读取", "发布机关与文件编号已核对", "适用地区和专业范围明确"]), _step("basis_acceptance", "纳入项目依据目录", ["cost_manager"], ["有效期与适用范围已确认", "本项目引用用途已记录"], "acceptance")],
    },
    "02": {
        "workflow_id": "WF02", "name": "投标工作流", "submit_roles": ["cost_manager", "cost_estimator", "document_controller"],
        "fields": [_field("tender_title", "招标项目名称"), _field("procurement_no", "招标编号"), _field("buyer", "招标人"), _field("bid_deadline", "投标截止时间", kind="date"), _field("scope", "投标范围"), _field("quantity_basis", "工程量/清单版本"), _field("price_basis", "价格及造价依据版本"), _field("bid_version", "投标报价版本")],
        "steps": [_step("tender_compliance", "招标与技术条件复核", ["technical_lead"], ["招标文件及答疑已归档", "范围、工期和主要约束已核对", "未决事项已列明"]), _step("quantity_price_review", "工程量与报价复核", ["cost_manager"], ["清单与工程量版本已锁定", "依据、价格口径和报价版本可追溯", "风险和偏差已记录"]), _step("bid_approval", "投标决策审批", ["project_manager"], ["报价方案已审阅", "风险处置和投标决策已记录"]), _step("submission_acceptance", "投标递交验收", ["document_controller"], ["递交文件包版本已归档", "递交时间及回执证据已保存"], "acceptance")],
    },
    "03": {
        "workflow_id": "WF03", "name": "中标工作流", "submit_roles": ["cost_manager", "cost_estimator", "document_controller"],
        "fields": [_field("award_no", "中标通知编号"), _field("award_date", "中标日期", kind="date"), _field("winner", "中标单位"), _field("tender_no", "对应招标编号"), _field("bid_version", "对应投标版本"), _field("contract_no", "合同编号"), _field("contract_amount", "合同金额（人工录入）", kind="decimal"), _field("contract_period", "合同工期/期限")],
        "steps": [_step("award_review", "中标与合同资料复核", ["cost_manager"], ["中标通知原件已核验", "投标承诺与合同差异已列出", "合同版本和金额已复核"]), _step("handover_approval", "项目合同基准审批", ["project_manager"], ["合同范围、工期和责任已确认", "需澄清事项已有责任人"]), _step("baseline_acceptance", "施工造价基准验收", ["cost_manager"], ["中标清单与合同版本已归档", "项目基准引用已建立"], "acceptance")],
    },
    "04": {
        "workflow_id": "WF04", "name": "施工中造价工作流", "submit_roles": ["cost_manager", "cost_estimator", "production_manager", "site_engineer", "surveyor"],
        "fields": [_field("event_no", "现场/变更事件编号"), _field("event_date", "发生日期", kind="date"), _field("event_type", "事件类型"), _field("contract_no", "合同/清单基准"), _field("scope", "事件与施工范围"), _field("quantity_basis", "实物量及计量依据"), _field("cost_impact", "造价影响（人工复核）", kind="decimal"), _field("external_order", "外部指令/签认状态")],
        "steps": [_step("site_quantity", "现场实物量确认", ["production_manager", "surveyor"], ["位置、范围和发生时间可追溯", "实测/计量证据已关联", "已标记未确认数量"]), _step("technical_review", "技术与合同条件复核", ["technical_lead"], ["技术依据和合同责任已核对", "变更边界与未决项已记录"]), _step("cost_review", "造价影响复核", ["cost_manager"], ["基准清单和依据版本已关联", "数量、单价口径及影响由人员复核", "未将候选金额当作批准金额"]), _step("change_approval", "变更/索赔审批", ["project_manager"], ["审批依据和责任已确认", "外部审批要求已标明"]), _step("change_acceptance", "施工造价成果验收", ["cost_manager"], ["有效签认及证据完整", "成果版本已留档并可交接"], "acceptance")],
    },
    "05": {
        "workflow_id": "WF05", "name": "竣工结算工作流", "submit_roles": ["cost_manager", "cost_estimator", "document_controller"],
        "fields": [_field("contract_no", "合同编号/版本"), _field("settlement_period", "结算范围与期间"), _field("submitted_amount", "送审金额（人工录入）", kind="decimal"), _field("reviewed_amount", "复核金额（人工录入）", kind="decimal"), _field("variance", "差异及争议说明"), _field("quantity_basis", "对量版本与依据"), _field("settlement_status", "外部审定状态"), _field("archive_package", "归档成果包版本")],
        "steps": [_step("settlement_measurement", "工程量与签证对量", ["cost_estimator"], ["合同清单和竣工图版本已锁定", "变更、签证和试验/质量证据已核对", "争议工程量已单列"]), _step("settlement_cost", "结算造价复核", ["cost_manager"], ["送审/审定口径分开记录", "计算依据和审核差异可追溯", "未决外审事项已列出"]), _step("settlement_approval", "结算结果审批", ["project_manager"], ["结算范围及责任已确认", "外部审定凭据与内部意见已区分"]), _step("settlement_archive", "竣工结算归档验收", ["document_controller"], ["完整成果包及版本已归档", "证据索引和遗留事项已移交"], "acceptance")],
    },
    "07": {
        "workflow_id": "WF07", "name": "工程量计算复核", "submit_roles": ["cost_manager", "cost_estimator", "surveyor", "technical_lead"],
        "fields": [_field("drawing_no", "图纸编号"), _field("drawing_version", "图纸版本"), _field("boq_code", "清单编码"), _field("item_name", "项目名称"), _field("unit", "计量单位"), _field("formula", "计算式/计量规则（人工提供）"), _field("quantity", "候选工程量", kind="decimal"), _field("comparison_basis", "对比口径/原结果版本")],
        "steps": [_step("quantity_check", "计算式与图纸复核", ["surveyor", "technical_lead"], ["图纸版本、比例/坐标和范围已核", "工程量计算式可复算", "单位及扣减规则已核对"]), _step("quantity_acceptance", "工程量结果专业验收", ["cost_manager"], ["候选结果与清单/基准差异已解释", "验收工程量由责任人确认并形成版本"], "acceptance")],
    },
    "08": {
        "workflow_id": "WF08", "name": "PDF/CAD/BIM 提量工具", "submit_roles": ["cost_manager", "cost_estimator", "surveyor", "technical_lead"],
        "fields": [_field("source_name", "源文件名称"), _field("source_version", "源文件版本"), _field("format", "文件格式（PDF/DXF/DWG/IFC 等）"), _field("discipline", "专业/构件范围"), _field("method", "提量方法/规则"), _field("scale_coordinate", "比例/坐标与单位"), _field("candidate_count", "候选量项数", kind="decimal"), _field("limitations", "识别缺陷与人工补量说明", required=False)],
        "steps": [_step("takeoff_review", "提量来源与方法复核", ["technical_lead", "surveyor"], ["原始文件及版本已固定", "单位、比例/坐标转换已核对", "工具覆盖不足和人工补量项已标明"]), _step("takeoff_acceptance", "工程量候选专业验收", ["cost_manager"], ["提量结果已逐项抽核", "不确定项未自动成为正式工程量", "通过项已形成可追溯结果版本"], "acceptance")],
    },
    "09": {
        "workflow_id": "WF09", "name": "施工项目试验报告系统", "submit_roles": ["lab_testing_officer", "quality_officer", "document_controller"],
        "fields": [_field("report_no", "试验/检测报告编号"), _field("lab", "试验检测机构"), _field("sample_no", "样品/取样编号"), _field("material", "材料/试验项目"), _field("location", "使用部位/批次"), _field("sample_date", "取样日期", kind="date"), _field("report_date", "报告日期", kind="date"), _field("conclusion", "报告结论（按原件录入）"), _field("retest_of", "复检关联报告", required=False)],
        "steps": [_step("report_review", "报告与样品绑定复核", ["quality_officer"], ["原始报告编号与机构已核", "样品、材料批次和部位绑定一致", "复检/不合格报告已建立关联"]), _step("technical_acceptance", "质量证据专业验收", ["quality_officer"], ["报告内容与质量验收责任已核", "系统未自动判定实体合格", "不合格及复检事项已记录"], "acceptance"), _step("report_archive", "试验资料归档验收", ["document_controller"], ["报告原件和索引已归档", "报告已关联相应施工/计量事件"], "acceptance")],
    },
}

NEXT_MODULES: dict[str, dict[str, str]] = {
    "02": {"03": "cost_manager"}, "03": {"04": "cost_manager"}, "04": {"05": "cost_manager"},
    "07": {"04": "production_manager"}, "08": {"07": "cost_estimator"}, "09": {"04": "quality_officer"},
}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DECIMAL_RE = re.compile(r"^-?\d{1,15}(?:\.\d{1,6})?$")


def canonical_hash(value: Mapping[str, Any]) -> str:
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def _summary(value: Mapping[str, Any]) -> str:
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(packed) > 1100:
        raise BusinessWorkflowError("操作摘要过长，请缩短说明")
    return packed


def _payload(event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(event.get("payload_summary", "{}")))
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _roles(actor: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in (actor.get("roles") or [actor.get("role", "")]) if str(value)}


_PROJECTION_KEYS = {"workflow_id", "workflow_name", "status", "status_label", "current_step", "completed_steps", "steps", "history", "latest_result_version", "submitted_by", "step_actors", "decision_note", "agent_ops_plan"}


def _stored_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in _PROJECTION_KEYS}


def _validate_fields(module_id: str, fields: Mapping[str, Any], *, complete: bool = False) -> dict[str, str]:
    spec = MODULES.get(module_id)
    if spec is None or not isinstance(fields, Mapping):
        raise BusinessWorkflowError("流程模块或字段格式无效")
    by_key = {item["key"]: item for item in spec["fields"]}
    if set(fields) - set(by_key):
        raise BusinessWorkflowError("包含该流程未定义的字段")
    clean: dict[str, str] = {}
    for key, raw in fields.items():
        if raw is None:
            continue
        value = str(raw).strip()
        if len(value) > 500:
            raise BusinessWorkflowError(f"{by_key[key]['label']}最多填写 500 个字符")
        if value:
            kind = by_key[key]["kind"]
            if kind == "date":
                if not _DATE_RE.fullmatch(value):
                    raise BusinessWorkflowError(f"{by_key[key]['label']}请使用 YYYY-MM-DD")
                try:
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise BusinessWorkflowError(f"{by_key[key]['label']}不是有效日期") from exc
            if kind == "decimal" and not _DECIMAL_RE.fullmatch(value):
                raise BusinessWorkflowError(f"{by_key[key]['label']}请输入明确的数字，不要添加单位或千位分隔符")
            clean[key] = value
    if complete:
        missing = [item["label"] for item in spec["fields"] if item["required"] and not clean.get(item["key"])]
        if missing:
            raise BusinessWorkflowError("提交前请补齐：" + "、".join(missing))
    return clean


def _evidence_refs(values: object) -> list[str]:
    if not isinstance(values, list):
        raise BusinessWorkflowError("证据必须选择本项目已归档资料")
    refs = [str(item).strip() for item in values]
    if len(refs) != len(set(refs)):
        raise BusinessWorkflowError("证据引用不能重复")
    if any(not re.fullmatch(r"sha256:[a-f0-9]{64}", item) for item in refs):
        raise BusinessWorkflowError("证据引用格式无效，请选择本项目已归档资料")
    return refs


def definitions() -> list[dict[str, Any]]:
    return [{"module_id": mid, **spec, "next_modules": list(NEXT_MODULES.get(mid, {}))} for mid, spec in MODULES.items()]


def _latest_record_blobs(state: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    blobs = state.get("business_workflow_blobs") or {}
    if not isinstance(blobs, Mapping):
        raise BusinessWorkflowError("流程成果存储格式异常")
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") != "RESULT_VERSIONED" or event.get("target_type") != "result_version":
            continue
        match = re.fullmatch(r"business_workflow_record_sha256=([a-f0-9]{64})", str(_payload(event).get("record_hash", "")))
        if not match:
            continue
        digest = match.group(1)
        value = blobs.get(digest)
        if not isinstance(value, Mapping) or canonical_hash(value) != digest:
            raise BusinessWorkflowError("流程成果哈希校验失败，已停止读取该项目流程")
        if str(value.get("run_id", "")) != str(event.get("run_id", "")):
            raise BusinessWorkflowError("流程成果与运行编号不一致")
        latest[str(value["run_id"])] = dict(value)
    return latest


def _project_runs(state: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = _latest_record_blobs(state, events)
    by_run: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("workflow_id") in {spec["workflow_id"] for spec in MODULES.values()}:
            by_run[str(event.get("run_id", ""))].append(event)
    result: list[dict[str, Any]] = []
    for run_id, history in by_run.items():
        record = records.get(run_id)
        if record is None:
            continue
        module_id = str(record.get("module_id", ""))
        spec = MODULES.get(module_id)
        if spec is None:
            raise BusinessWorkflowError("流程模块编号无效")
        status = "draft"
        current_step = ""
        completed_steps: list[str] = []
        submitted_by = ""
        step_actors: list[str] = []
        rejected_reason = ""
        for event in history:
            summary = _payload(event)
            etype = str(event.get("event_type", ""))
            if etype == "INPUT_VALIDATED" and summary.get("action") == "submit":
                status = "review"
                current_step = str((spec.get("steps") or [{}])[0].get("key", ""))
                completed_steps = []
                step_actors = []
                submitted_by = str(event.get("actor_id", ""))
            elif etype == "HUMAN_GATE_OPENED":
                current_step = str(summary.get("step", ""))
                if current_step:
                    status = "review"
            elif etype == "HUMAN_GATE_RESOLVED":
                step = str(summary.get("step", ""))
                decision = str(summary.get("decision", ""))
                current_step = ""
                if decision == "approve":
                    if step and step not in completed_steps:
                        completed_steps.append(step)
                    step_actors.append(str(event.get("actor_id", "")))
                    status = "review"
                elif decision == "return":
                    status = "needs_correction"
                    rejected_reason = str(summary.get("note", ""))
                elif decision == "reject":
                    status = "rejected"
                    rejected_reason = str(summary.get("note", ""))
            elif etype == "ACCEPTANCE_RECORDED":
                status = "accepted"
                current_step = ""
                step_actors.append(str(event.get("actor_id", "")))
            elif etype == "FAILURE_RECORDED" and summary.get("failure_class") == "workflow_blocked":
                status = "blocked"
                rejected_reason = str(summary.get("reason", "工作流被阻断"))
        version_id = ""
        for event in history:
            if event.get("event_type") == "RESULT_VERSIONED" and event.get("target_type") == "result_version" and str(_payload(event).get("record_hash", "")).startswith("business_workflow_record_sha256="):
                version_id = str(event.get("target_id", ""))
        result.append({
            **record,
            "workflow_id": spec["workflow_id"], "workflow_name": spec["name"], "status": status,
            "status_label": {"draft": "草稿", "review": "待复核/审批", "needs_correction": "待补正", "rejected": "已退回终止", "accepted": "已验收", "blocked": "已阻断"}.get(status, status),
            "current_step": current_step, "completed_steps": completed_steps,
            "steps": spec["steps"], "history": [dict(event) for event in history],
            "latest_result_version": version_id, "submitted_by": submitted_by,
            "step_actors": step_actors, "decision_note": rejected_reason,
            "agent_ops_plan": next(({"state": str(event.get("agent_ops_state", "")), "meaning": str(event.get("agent_ops_state_meaning", "")), "updated_at": str(event.get("occurred_at", ""))} for event in reversed(history) if event.get("event_type") == "AGENT_OPS_PLAN_RECORDED"), {"state": "NOT_CREATED", "meaning": "仅说明尚未生成计划"}),
        })
    result.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return result


def _event_fields(project_id: str, run_id: str, module_id: str, event_type: str, actor: Mapping[str, Any], *, target_type: str, target_id: str, summary: Mapping[str, Any], idempotency_key: str, evidence_refs: Sequence[str] = (), result_version_refs: Sequence[str] = (), checkpoint_ref: str = "", agent_ops_state: str = "") -> dict[str, Any]:
    result = {
        "project_id": project_id, "run_id": run_id, "workflow_id": f"WF{module_id}", "module_id": module_id,
        "event_type": event_type, "actor_type": "human", "actor_id": str(actor.get("id", "")),
        "target_type": target_type, "target_id": target_id, "payload_summary": _summary({**summary, "actor_role": str(actor.get("role", ""))}),
        "evidence_refs": list(evidence_refs), "result_version_refs": list(result_version_refs),
        "checkpoint_ref": checkpoint_ref, "idempotency_key": idempotency_key,
        "data_classification": "Restricted",
    }
    if agent_ops_state:
        result["agent_ops_state"] = agent_ops_state
    return result


class BusinessWorkflowService:
    """Human-gated, append-only business flow service for one local project."""

    def __init__(self, workspace: Any) -> None:
        self.workspace = workspace

    def snapshot(self, project_id: str, *, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        ledger = self.workspace.execution_ledger_snapshot(project_id)
        state = self.workspace.load(project_id) or {}
        runs = _project_runs(state, ledger["events"])
        sources = []
        for source in state.get("sources") or []:
            if not isinstance(source, Mapping) or source.get("status") == "deleted":
                continue
            digest = str(source.get("content_hash", "")).lower()
            if re.fullmatch(r"[a-f0-9]{64}", digest):
                sources.append({"name": str(source.get("name", source.get("source_id", "资料"))), "reference": f"sha256:{digest}"})
        consumed = {str(item.get("target_id", "")) for item in ledger["events"] if item.get("event_type") == "HANDOFF_CONSUMED"}
        handoffs = []
        for event in ledger["events"]:
            if event.get("event_type") != "HANDOFF_CREATED" or str(event.get("target_id", "")) in consumed:
                continue
            summary = _payload(event)
            handoffs.append({"handoff_id": str(event.get("target_id", "")), "source_run_id": str(summary.get("source_run_id", "")), "source_module_id": str(summary.get("source_module_id", "")), "target_module_id": str(summary.get("target_module_id", "")), "recipient_role": str(summary.get("recipient_role", "")), "created_at": str(event.get("occurred_at", ""))})
        return {"modules": definitions(), "runs": runs, "handoffs": handoffs, "evidence_sources": sources, "recovery": {"status": "replayed", "source": "verified_local_execution_ledger", "event_count": ledger["event_count"]}, "ledger": {"valid": ledger["valid"], "event_count": ledger["event_count"], "last_event_hash": ledger["last_event_hash"]}}

    def apply(self, project_id: str, actor: Mapping[str, Any], payload: object) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise BusinessWorkflowError("流程操作格式无效")
        if not str(actor.get("id", "")):
            raise BusinessWorkflowError("登录身份缺少人员编号")
        action = str(payload.get("action", "")).strip()
        operation_key = str(payload.get("idempotency_key", "")).strip()
        if not operation_key or len(operation_key) > 128:
            raise BusinessWorkflowError("操作缺少有效的幂等编号，请刷新后重试")
        module_id = str(payload.get("module_id", "")).strip()
        if module_id not in MODULES:
            raise BusinessWorkflowError("请选择 01–09 中的业务流程（06 为共享底座服务，不单独建业务单）")
        spec = MODULES[module_id]
        snapshot = self.workspace.execution_ledger_snapshot(project_id)
        if any(
            str(event.get("actor_id", "")) == str(actor["id"])
            and str(event.get("idempotency_key", "")).startswith(f"{operation_key}:")
            for event in snapshot["events"]
        ):
            return self.snapshot(project_id, actor=actor)
        state = self.workspace.load(project_id) or {}
        current_runs = _project_runs(state, snapshot["events"])
        by_id = {str(item["run_id"]): item for item in current_runs}
        run_id = str(payload.get("run_id", "")).strip()
        record_blobs: dict[str, dict[str, Any]] = {}
        new_events: list[dict[str, Any]] = []
        actor_id = str(actor["id"])
        actor_roles = _roles(actor)

        def append_record(record: dict[str, Any], version: int, *, action_event: str, summary: Mapping[str, Any], event_evidence: Sequence[str] = ()) -> str:
            record = {**_stored_record(record), "version": version, "updated_at": datetime.now(timezone.utc).isoformat()}
            digest = canonical_hash(record)
            record_blobs[digest] = record
            version_id = f"wf-{record['run_id']}-v{version}"
            new_events.append(_event_fields(project_id, str(record["run_id"]), module_id, "RESULT_VERSIONED", actor, target_type="result_version", target_id=version_id, summary={"record_hash": f"business_workflow_record_sha256={digest}", "revision": version}, idempotency_key=f"{payload.get('idempotency_key','')}:record:{version}", evidence_refs=event_evidence))
            refs = [f"result-version:{version_id}"]
            if action_event:
                new_events.append(_event_fields(project_id, str(record["run_id"]), module_id, action_event, actor, target_type="workflow", target_id=str(record["run_id"]), summary={**summary, "record_version": version_id}, idempotency_key=f"{payload.get('idempotency_key','')}:{action_event}:{version}", result_version_refs=refs))
            return version_id

        if action == "create":
            if not (actor_roles & set(spec["submit_roles"])):
                raise BusinessWorkflowError("当前岗位不能发起该业务流程")
            fields = _validate_fields(module_id, payload.get("fields") or {})
            refs = _evidence_refs(payload.get("evidence_refs", []))
            run_id = f"{module_id}-{uuid4().hex[:16]}"
            record = {"run_id": run_id, "project_id": project_id, "module_id": module_id, "title": spec["name"], "fields": fields, "evidence_refs": refs, "created_by": actor_id, "created_by_name": str(actor.get("display_name", actor.get("username", ""))), "created_by_role": str(actor.get("role", "")), "created_at": datetime.now(timezone.utc).isoformat()}
            new_events.append(_event_fields(project_id, run_id, module_id, "RUN_CREATED", actor, target_type="workflow", target_id=run_id, summary={"action": "created", "module": module_id}, idempotency_key=f"{payload.get('idempotency_key','')}:created"))
            new_events.append(_event_fields(project_id, run_id, module_id, "AGENT_OPS_PLAN_RECORDED", actor, target_type="workflow", target_id=run_id, summary={"planner": "Sayelf Agent Ops 最小计划", "planning_only": True, "next": "等待补齐表单和证据"}, idempotency_key=f"{payload.get('idempotency_key','')}:agentops:scoped", agent_ops_state="SCOPED"))
            append_record(record, 1, action_event="INPUT_REGISTERED", summary={"action": "draft_created"}, event_evidence=refs)
        else:
            record = by_id.get(run_id) if action != "consume_handoff" else None
            if action != "consume_handoff" and (record is None or str(record.get("module_id", "")) != module_id):
                raise BusinessWorkflowError("该流程记录不存在或模块不匹配")
            status = str(record.get("status", "")) if record else ""
            if action == "update":
                if status not in {"draft", "needs_correction"} or actor_id != str(record.get("created_by", "")):
                    raise BusinessWorkflowError("仅流程发起人可编辑草稿或补正中的记录")
                if not (actor_roles & set(spec["submit_roles"])):
                    raise BusinessWorkflowError("当前岗位不能修改该业务流程")
                fields = dict(record.get("fields") or {})
                fields.update(_validate_fields(module_id, payload.get("fields") or {}))
                refs = _evidence_refs(payload.get("evidence_refs", record.get("evidence_refs", [])))
                updated = {**_stored_record(record), "fields": fields, "evidence_refs": refs}
                append_record(updated, int(record.get("version", 1)) + 1, action_event="INPUT_REGISTERED", summary={"action": "record_updated"}, event_evidence=refs)
            elif action == "submit":
                if status not in {"draft", "needs_correction"}:
                    raise BusinessWorkflowError("该流程当前状态不能提交")
                if actor_id != str(record.get("created_by", "")) or not (actor_roles & set(spec["submit_roles"])):
                    raise BusinessWorkflowError("只有有权发起的原责任人可以提交")
                _validate_fields(module_id, record.get("fields") or {}, complete=True)
                refs = _evidence_refs(record.get("evidence_refs", []))
                if not refs:
                    raise BusinessWorkflowError("提交前至少关联一份本项目已归档原始资料")
                version_id = str(record.get("latest_result_version", ""))
                if not version_id:
                    raise BusinessWorkflowError("流程记录版本缺失")
                first_step = spec["steps"][0]
                new_events.append(_event_fields(project_id, run_id, module_id, "AGENT_OPS_PLAN_RECORDED", actor, target_type="workflow", target_id=run_id, summary={"planner": "Sayelf Agent Ops 最小计划", "planning_only": True, "plan_steps": [item["key"] for item in spec["steps"]], "warning": "READY 仅表示计划就绪，不代表执行或验收"}, idempotency_key=f"{payload.get('idempotency_key','')}:agentops:ready", agent_ops_state="READY"))
                new_events.append(_event_fields(project_id, run_id, module_id, "INPUT_VALIDATED", actor, target_type="workflow", target_id=run_id, summary={"action": "submit", "required_fields": len(spec["fields"])}, idempotency_key=f"{payload.get('idempotency_key','')}:submit", result_version_refs=[f"result-version:{version_id}"], evidence_refs=refs))
                new_events.append(_event_fields(project_id, run_id, module_id, "HUMAN_GATE_OPENED", actor, target_type="workflow", target_id=run_id, summary={"step": first_step["key"], "label": first_step["label"]}, idempotency_key=f"{payload.get('idempotency_key','')}:open:{first_step['key']}"))
            elif action == "decide":
                if status != "review":
                    raise BusinessWorkflowError("流程当前没有待处理的人工审核")
                step_key = str(payload.get("step", "")).strip()
                step = next((item for item in spec["steps"] if item["key"] == step_key), None)
                if step is None or step_key != str(record.get("current_step", "")):
                    raise BusinessWorkflowError("审核步骤已变化，请刷新后重试")
                if not (actor_roles & set(step["roles"])):
                    raise BusinessWorkflowError("当前岗位不承担此步骤的审核/验收")
                if actor_id == str(record.get("created_by", "")) or actor_id in set(record.get("step_actors", [])):
                    raise BusinessWorkflowError("流程发起人或已签署此流程的人员不能重复审批/验收")
                decision = str(payload.get("decision", "")).strip()
                if decision not in {"approve", "return", "reject"}:
                    raise BusinessWorkflowError("审核结论无效")
                note = str(payload.get("note", "")).strip()
                if decision in {"return", "reject"} and not note:
                    raise BusinessWorkflowError("退回或拒绝时必须填写原因")
                if len(note) > 400:
                    raise BusinessWorkflowError("审核说明最多 400 个字符")
                checklist = payload.get("checklist") or {}
                if not isinstance(checklist, Mapping) or set(checklist) != set(step["checks"]):
                    raise BusinessWorkflowError("必须逐项回应本步骤的专业验收清单")
                if decision == "approve" and any(checklist.get(key) is not True for key in step["checks"]):
                    raise BusinessWorkflowError("专业验收清单未全部确认，不能通过；请退回补正")
                refs = _evidence_refs(payload.get("evidence_refs", []))
                if decision == "approve" and not refs:
                    raise BusinessWorkflowError("审批/验收必须关联至少一份本项目证据")
                next_record = _stored_record(record)
                version_id = append_record(next_record, int(record.get("version", 1)) + 1, action_event="HUMAN_GATE_RESOLVED", summary={"step": step_key, "decision": decision, "note": note, "checklist": dict(checklist)}, event_evidence=refs)
                if decision == "return":
                    new_events.append(_event_fields(project_id, run_id, module_id, "FAILURE_RECORDED", actor, target_type="workflow", target_id=run_id, summary={"failure_class": "workflow_return", "reason": note}, idempotency_key=f"{payload.get('idempotency_key','')}:return", checkpoint_ref=self._latest_checkpoint(run_id, snapshot["events"])))
                elif decision == "approve":
                    index = next(i for i, item in enumerate(spec["steps"]) if item["key"] == step_key)
                    if step["kind"] == "acceptance" and index == len(spec["steps"]) - 1:
                        new_events.append(_event_fields(project_id, run_id, module_id, "ACCEPTANCE_RECORDED", actor, target_type="workflow", target_id=run_id, summary={"step": step_key, "status": "accepted", "checklist": dict(checklist)}, idempotency_key=f"{payload.get('idempotency_key','')}:accepted", result_version_refs=[f"result-version:{version_id}"], evidence_refs=refs))
                    elif index + 1 < len(spec["steps"]):
                        next_step = spec["steps"][index + 1]
                        new_events.append(_event_fields(project_id, run_id, module_id, "HUMAN_GATE_OPENED", actor, target_type="workflow", target_id=run_id, summary={"step": next_step["key"], "label": next_step["label"]}, idempotency_key=f"{payload.get('idempotency_key','')}:open:{next_step['key']}"))
                if decision == "reject":
                    pass
            elif action == "handoff":
                if status != "accepted":
                    raise BusinessWorkflowError("只有已通过专业验收的流程可以正式交接")
                target_module = str(payload.get("target_module_id", "")).strip()
                allowed = NEXT_MODULES.get(module_id, {})
                recipient_role = allowed.get(target_module)
                if not recipient_role:
                    raise BusinessWorkflowError("该流程没有已定义的下游接收岗位/流程")
                if not (actor_roles & {"cost_manager", "project_manager"}):
                    raise BusinessWorkflowError("交接发起需要项目经理或造价经理岗位")
                handoff_id = f"HO-{uuid4().hex[:12]}"
                version_id = str(record.get("latest_result_version", ""))
                new_events.append(_event_fields(project_id, run_id, module_id, "HANDOFF_CREATED", actor, target_type="handoff", target_id=handoff_id, summary={"source_run_id": run_id, "source_module_id": module_id, "target_module_id": target_module, "recipient_role": recipient_role, "allowed_use": "下游流程参考；仍需重新复核"}, idempotency_key=f"{payload.get('idempotency_key','')}:handoff:{handoff_id}", result_version_refs=[f"result-version:{version_id}"]))
            elif action == "consume_handoff":
                handoff_id = str(payload.get("handoff_id", "")).strip()
                created = next((item for item in snapshot["events"] if item.get("event_type") == "HANDOFF_CREATED" and item.get("target_id") == handoff_id), None)
                if created is None or str(created.get("project_id", "")) != project_id:
                    raise BusinessWorkflowError("待接收交接不存在")
                if any(item.get("event_type") == "HANDOFF_CONSUMED" and item.get("target_id") == handoff_id for item in snapshot["events"]):
                    raise BusinessWorkflowError("该交接已被签收，不能重复接收")
                handoff = _payload(created)
                if str(handoff.get("target_module_id", "")) != module_id or not (actor_roles & {str(handoff.get("recipient_role", ""))}):
                    raise BusinessWorkflowError("当前模块或岗位不是指定接收方")
                if actor_id == str(created.get("actor_id", "")):
                    raise BusinessWorkflowError("交接发起人不能自行签收")
                new_events.append(_event_fields(project_id, str(handoff.get("source_run_id", "")), f"{str(handoff.get('source_module_id',''))}", "HANDOFF_CONSUMED", actor, target_type="handoff", target_id=handoff_id, summary={"source_run_id": handoff.get("source_run_id"), "target_module_id": module_id, "recipient_role": handoff.get("recipient_role"), "accepted_for_review": True}, idempotency_key=f"{payload.get('idempotency_key','')}:consume:{handoff_id}"))
            else:
                raise BusinessWorkflowError("不支持的流程操作")

        # Bind each state-changing action to a durable recovery point. The
        # projection is rebuilt from the verified event stream after restart.
        if new_events and run_id and action not in {"consume_handoff"}:
            checkpoint_id = f"CP-{run_id}-{len(snapshot['events']) + len(new_events) + 1}"
            new_events.append(_event_fields(project_id, run_id, module_id, "CHECKPOINT_CREATED", actor, target_type="checkpoint", target_id=checkpoint_id, summary={"source": "business_workflow_snapshot", "recoverable_from": "verified_event_ledger"}, idempotency_key=f"{payload.get('idempotency_key','')}:checkpoint"))
        expected_hash = str(snapshot.get("last_event_hash", ""))
        self.workspace.append_workflow_batch(project_id, new_events, record_blobs, expected_last_event_hash=expected_hash)
        return self.snapshot(project_id, actor=actor)

    @staticmethod
    def _latest_checkpoint(run_id: str, events: Sequence[Mapping[str, Any]]) -> str:
        matches = [item for item in events if item.get("run_id") == run_id and item.get("event_type") == "CHECKPOINT_CREATED"]
        return f"checkpoint:{matches[-1]['target_id']}" if matches else ""
