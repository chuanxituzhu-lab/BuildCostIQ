"""Pure event rules for the local S06 execution ledger.

The ledger records work state; it does not execute skills or grant approval.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any
from uuid import uuid4


GENESIS_HASH = "0" * 64
MODULE_IDS = frozenset(f"{index:02d}" for index in range(1, 10))
EVENT_TYPES = frozenset(
    {
        "RUN_CREATED",
        "INPUT_REGISTERED",
        "INPUT_VALIDATED",
        "SKILL_STARTED",
        "SKILL_COMPLETED",
        "RESULT_CREATED",
        "RESULT_VERSIONED",
        "EVIDENCE_ATTACHED",
        "ACCEPTANCE_RECORDED",
        "HUMAN_GATE_OPENED",
        "HUMAN_GATE_RESOLVED",
        "HANDOFF_CREATED",
        "HANDOFF_CONSUMED",
        "FAILURE_RECORDED",
        "CHECKPOINT_CREATED",
        "RECOVERY_STARTED",
        "RECOVERY_COMPLETED",
        "RUN_BLOCKED",
        "AGENT_OPS_PLAN_RECORDED",
    }
)
ACTOR_TYPES = frozenset({"human", "agent", "connector", "system"})
DATA_CLASSIFICATIONS = frozenset({"Sensitive", "Restricted", "Unknown"})
AGENT_OPS_STATES = frozenset({"INBOX", "SCOPED", "WORKING", "READY"})
_HASH = re.compile(r"^[a-f0-9]{64}$")
_IDEMPOTENCY_FIELDS = (
    "project_id",
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
    "agent_ops_state_meaning",
)


class ExecutionLedgerError(ValueError):
    """Raised when a run event is invalid or its chain cannot be trusted."""


def _text(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ExecutionLedgerError(f"运行记录缺少{field}")
    return result


def _unique_refs(values: Sequence[object] | None, field: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ExecutionLedgerError(f"{field}必须是引用列表")
    refs = [str(value).strip() for value in (values or [])]
    if any(not item for item in refs):
        raise ExecutionLedgerError(f"{field}不能包含空引用")
    if len(set(refs)) != len(refs):
        raise ExecutionLedgerError(f"{field}不能重复")
    return refs


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def execution_event_hash(event: Mapping[str, Any]) -> str:
    """Hash one event without its own hash field."""
    payload = {key: value for key, value in event.items() if key != "event_hash"}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _validate_event_shape(event: Mapping[str, Any], project_id: str | None = None) -> None:
    required = (
        "schema_version",
        "project_id",
        "event_id",
        "run_id",
        "workflow_id",
        "module_id",
        "event_type",
        "occurred_at",
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
        "record_authority",
        "previous_event_hash",
        "event_hash",
    )
    for field in required:
        if field not in event:
            raise ExecutionLedgerError(f"运行记录缺少字段：{field}")
        if field not in {"evidence_refs", "result_version_refs", "checkpoint_ref"}:
            _text(event.get(field), field)
    allowed = set(required) | {"agent_ops_state", "agent_ops_state_meaning"}
    if set(event) - allowed:
        raise ExecutionLedgerError("运行记录包含不受支持的字段")
    if event.get("schema_version") != "1.0.0":
        raise ExecutionLedgerError("运行记录版本不受支持")
    if project_id is not None and event.get("project_id") != project_id:
        raise ExecutionLedgerError("运行记录项目范围不一致")
    if event.get("module_id") not in MODULE_IDS or event.get("workflow_id") != f"WF{event.get('module_id')}":
        raise ExecutionLedgerError("运行记录模块/工作流引用不匹配")
    if event.get("event_type") not in EVENT_TYPES:
        raise ExecutionLedgerError("运行记录事件类型不受支持")
    if event.get("actor_type") not in ACTOR_TYPES:
        raise ExecutionLedgerError("运行记录操作者类型不受支持")
    if event.get("data_classification") not in DATA_CLASSIFICATIONS:
        raise ExecutionLedgerError("运行记录只能标为敏感、受限或待分类")
    if event.get("record_authority") != "candidate":
        raise ExecutionLedgerError("运行事件仅能记录候选状态，不能授予业务权威")
    if not isinstance(event.get("evidence_refs"), list) or not isinstance(event.get("result_version_refs"), list):
        raise ExecutionLedgerError("证据与结果版本引用必须是列表")
    if not _HASH.fullmatch(str(event.get("previous_event_hash", ""))):
        raise ExecutionLedgerError("前序哈希格式无效")
    if not _HASH.fullmatch(str(event.get("event_hash", ""))):
        raise ExecutionLedgerError("当前事件哈希格式无效")
    try:
        occurred_at = datetime.fromisoformat(str(event.get("occurred_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionLedgerError("运行记录时间格式无效") from exc
    if occurred_at.tzinfo is None:
        raise ExecutionLedgerError("运行记录时间必须包含时区")
    summary = str(event.get("payload_summary", ""))
    if len(summary) > 1200 or "\n" in summary or "\r" in summary:
        raise ExecutionLedgerError("运行记录摘要格式无效")
    _unique_refs(event.get("evidence_refs"), "证据引用")
    _unique_refs(event.get("result_version_refs"), "结果版本引用")

    plan_event = event.get("event_type") == "AGENT_OPS_PLAN_RECORDED"
    agent_state = event.get("agent_ops_state")
    meaning = event.get("agent_ops_state_meaning")
    if plan_event:
        if agent_state not in AGENT_OPS_STATES:
            raise ExecutionLedgerError("Agent Ops 计划事件缺少有效状态")
        expected_meaning = "plan_ready_only" if agent_state == "READY" else "planning_state_only"
        if meaning != expected_meaning:
            raise ExecutionLedgerError("Agent Ops 状态语义不匹配，READY 仅表示计划就绪")
    elif agent_state is not None or meaning is not None:
        raise ExecutionLedgerError("Agent Ops 计划状态只能出现在计划记录事件中")


def create_execution_event(
    *,
    project_id: str,
    run_id: str,
    workflow_id: str,
    module_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str,
    target_type: str,
    target_id: str,
    payload_summary: str,
    evidence_refs: Sequence[object] | None = None,
    result_version_refs: Sequence[object] | None = None,
    checkpoint_ref: str | None = None,
    idempotency_key: str,
    data_classification: str = "Restricted",
    previous_event_hash: str = GENESIS_HASH,
    agent_ops_state: str | None = None,
) -> dict[str, Any]:
    """Build and hash one validated event. Raw files and credentials are never fields."""
    summary = _text(payload_summary, "摘要")
    if len(summary) > 1200 or "\n" in summary or "\r" in summary:
        raise ExecutionLedgerError("摘要需为不超过 1200 字的单行文本")
    event = {
        "schema_version": "1.0.0",
        "project_id": _text(project_id, "项目编号"),
        "event_id": str(uuid4()),
        "run_id": _text(run_id, "运行编号"),
        "workflow_id": _text(workflow_id, "工作流编号"),
        "module_id": _text(module_id, "模块编号"),
        "event_type": _text(event_type, "事件类型"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "actor_type": _text(actor_type, "操作者类型"),
        "actor_id": _text(actor_id, "操作者编号"),
        "target_type": _text(target_type, "目标类型"),
        "target_id": _text(target_id, "目标编号"),
        "payload_summary": summary,
        "evidence_refs": _unique_refs(evidence_refs, "证据引用"),
        "result_version_refs": _unique_refs(result_version_refs, "结果版本引用"),
        "checkpoint_ref": str(checkpoint_ref or "").strip(),
        "idempotency_key": _text(idempotency_key, "幂等键"),
        "data_classification": _text(data_classification, "数据分类"),
        "record_authority": "candidate",
        "previous_event_hash": str(previous_event_hash),
    }
    if event_type == "AGENT_OPS_PLAN_RECORDED":
        if agent_ops_state not in AGENT_OPS_STATES:
            raise ExecutionLedgerError("Agent Ops 计划事件缺少有效状态")
        event["agent_ops_state"] = agent_ops_state
        event["agent_ops_state_meaning"] = "plan_ready_only" if agent_ops_state == "READY" else "planning_state_only"
    elif agent_ops_state is not None:
        raise ExecutionLedgerError("Agent Ops 计划状态只能出现在计划记录事件中")
    _validate_event_shape({**event, "event_hash": "0" * 64}, project_id=project_id)
    event["event_hash"] = execution_event_hash(event)
    return event


def idempotency_fingerprint(event: Mapping[str, Any]) -> tuple[Any, ...]:
    """Fields that must match when the same logical event is retried."""
    return tuple(json.dumps(event.get(field), ensure_ascii=False, sort_keys=True) for field in _IDEMPOTENCY_FIELDS)


def derive_agent_ops_plan_states(events: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Project the latest planning-only state per run from a verified event list."""
    latest_by_run: dict[str, dict[str, str]] = {}
    for event in events:
        if event.get("event_type") != "AGENT_OPS_PLAN_RECORDED":
            continue
        run_id = str(event.get("run_id", ""))
        latest_by_run[run_id] = {
            "run_id": run_id,
            "workflow_id": str(event.get("workflow_id", "")),
            "module_id": str(event.get("module_id", "")),
            "target_type": str(event.get("target_type", "")),
            "target_id": str(event.get("target_id", "")),
            "state": str(event.get("agent_ops_state", "")),
            "state_meaning": str(event.get("agent_ops_state_meaning", "")),
            "updated_at": str(event.get("occurred_at", "")),
        }
    return [latest_by_run[run_id] for run_id in sorted(latest_by_run)]


def validate_execution_transition(
    prior_events: Sequence[Mapping[str, Any]], event: Mapping[str, Any]
) -> None:
    """Validate new checkpoint, recovery and handoff events against prior state.

    This validates record relationships only. It does not load checkpoint
    content, restore workflow state, assign handoff recipients, or authorize
    business work; historical event semantics are deliberately not revalidated.
    """
    run_id = str(event.get("run_id", ""))
    event_type = str(event.get("event_type", ""))
    checkpoint_ref = str(event.get("checkpoint_ref", "") or "").strip()
    same_run = [item for item in prior_events if str(item.get("run_id", "")) == run_id]

    if event_type == "CHECKPOINT_CREATED":
        if event.get("target_type") != "checkpoint":
            raise ExecutionLedgerError("检查点事件的目标类型必须为 checkpoint")
        if checkpoint_ref:
            raise ExecutionLedgerError("新建检查点事件不能引用自身检查点")
        if any(
            item.get("event_type") == "CHECKPOINT_CREATED"
            and item.get("target_type") == "checkpoint"
            and str(item.get("target_id", "")) == str(event.get("target_id", ""))
            for item in same_run
        ):
            raise ExecutionLedgerError("同一运行内检查点编号不能重复")
        return

    if checkpoint_ref:
        prefix = "checkpoint:"
        checkpoint_id = checkpoint_ref[len(prefix):] if checkpoint_ref.startswith(prefix) else ""
        if not checkpoint_id or not any(
            item.get("event_type") == "CHECKPOINT_CREATED"
            and item.get("target_type") == "checkpoint"
            and str(item.get("target_id", "")) == checkpoint_id
            for item in same_run
        ):
            raise ExecutionLedgerError("检查点引用必须指向本运行中更早登记的检查点")
    elif event_type in {"RECOVERY_STARTED", "RECOVERY_COMPLETED"}:
        raise ExecutionLedgerError("恢复事件必须引用本运行的检查点")

    if event_type in {"RECOVERY_STARTED", "RECOVERY_COMPLETED"}:
        recovery_open = False
        for prior in same_run:
            if str(prior.get("checkpoint_ref", "") or "").strip() != checkpoint_ref:
                continue
            prior_type = prior.get("event_type")
            if prior_type == "RECOVERY_STARTED":
                recovery_open = True
            elif prior_type == "RECOVERY_COMPLETED" or prior_type == "FAILURE_RECORDED":
                recovery_open = False

        if event_type == "RECOVERY_STARTED" and recovery_open:
            raise ExecutionLedgerError("该检查点已有未结束的恢复尝试")
        if event_type == "RECOVERY_COMPLETED" and not recovery_open:
            raise ExecutionLedgerError("恢复完成事件缺少同一检查点上尚未结束的恢复记录")

    if event_type in {"HANDOFF_CREATED", "HANDOFF_CONSUMED"}:
        if event.get("target_type") != "handoff":
            raise ExecutionLedgerError("交接事件的目标类型必须为 handoff")
        handoff_id = str(event.get("target_id", ""))
        prior_created = any(
            item.get("event_type") == "HANDOFF_CREATED"
            and item.get("target_type") == "handoff"
            and str(item.get("target_id", "")) == handoff_id
            for item in same_run
        )
        prior_consumed = any(
            item.get("event_type") == "HANDOFF_CONSUMED"
            and item.get("target_type") == "handoff"
            and str(item.get("target_id", "")) == handoff_id
            for item in same_run
        )
        if event_type == "HANDOFF_CREATED" and prior_created:
            raise ExecutionLedgerError("同一运行内交接编号不能重复创建")
        if event_type == "HANDOFF_CONSUMED" and not prior_created:
            raise ExecutionLedgerError("接收事件必须指向本运行中更早创建的交接")
        if event_type == "HANDOFF_CONSUMED" and prior_consumed:
            raise ExecutionLedgerError("同一交接只能记录一次接收")


def verify_execution_chain(events: Sequence[Mapping[str, Any]], project_id: str | None = None) -> str:
    """Validate the complete chain and return its last hash (or genesis hash)."""
    previous_hash = GENESIS_HASH
    seen_event_ids: set[str] = set()
    idempotency_keys: dict[tuple[str, str], tuple[Any, ...]] = {}
    for index, event in enumerate(events):
        _validate_event_shape(event, project_id=project_id)
        event_id = str(event.get("event_id", ""))
        if not event_id or event_id in seen_event_ids:
            raise ExecutionLedgerError(f"运行账本第 {index + 1} 条记录的事件编号为空或重复")
        seen_event_ids.add(event_id)
        if event.get("previous_event_hash") != previous_hash:
            raise ExecutionLedgerError(f"运行账本第 {index + 1} 条记录的前序哈希不匹配")
        calculated_hash = execution_event_hash(event)
        if event.get("event_hash") != calculated_hash:
            raise ExecutionLedgerError(f"运行账本第 {index + 1} 条记录哈希校验失败")
        key = (str(event.get("run_id")), str(event.get("idempotency_key")))
        fingerprint = idempotency_fingerprint(event)
        if key in idempotency_keys and idempotency_keys[key] != fingerprint:
            raise ExecutionLedgerError("运行账本存在冲突的幂等键")
        if key in idempotency_keys:
            raise ExecutionLedgerError("运行账本存在重复的幂等记录")
        idempotency_keys[key] = fingerprint
        previous_hash = calculated_hash
    return previous_hash
