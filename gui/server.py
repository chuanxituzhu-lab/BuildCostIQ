from __future__ import annotations

import argparse
import copy
import csv
import html
import io
import json
import mimetypes
import os
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping
from urllib.parse import parse_qs, quote, unquote, urlsplit
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from adapters import (
    BASIS_CATEGORIES,
    CategorizedArchiveStore,
    CONTRACT_VERSION,
    LINE_CONTRACTS,
    line_responsibility,
    LINE_IDS,
    LINE_LABELS,
    CoordinationError,
    DeploymentConfig,
    DeploymentStorageAdapter,
    ImmutableSourceStore,
    LocalBasisWorkspace,
    LocalAuthStore,
    LocalProjectWorkspace,
    ROLE_COST_MANAGER,
    ROLE_PERMISSIONS,
    ROLE_PROJECT_MANAGER,
    LineContractError,
    confirm_decision,
    confirm_line_records,
    coordination_snapshot,
    mapping_for_confirmed_record,
    new_decision,
    new_relation,
    new_task,
    preview_line_records,
    role_flow_contracts,
    update_task,
)
from adapters.connectors import build_project_bundle, connector_catalog
from adapters.recognition import RecognitionError, recognition_catalog, recognize_source
from adapters.search import build_evidence_answer, search_local_evidence
from core import (
    DIMENSIONS,
    OUTCOME_ALLOWED_TRANSITIONS,
    OUTCOME_STATUSES,
    OUTCOME_TYPES,
    EVENT_SOURCE_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    SEVERITIES,
    EventKernelError,
    build_state_vector,
    build_outcome_vector,
    compute_value_leaks,
    distill_local_data,
    distill_text,
    evaluate_event_rules,
    ensure_outcome_track,
    fuse_distillations,
    new_event,
    record_outcome_snapshot,
    run_cross_check,
    transition_event,
    transition_outcome,
    validate_event,
    Runtime,
)
from core.version import current_version
from core.models import SourceDocument
from plugins import build_default_plugins


STATIC_ROOT = Path(__file__).resolve().parent / "static"
RUNTIME = Runtime(build_default_plugins())
MAX_BODY_BYTES = 50_000_000
DEPLOYMENT_CONFIG: DeploymentConfig
DEPLOYMENT_STORAGE: DeploymentStorageAdapter
PROJECT_WORKSPACE: LocalProjectWorkspace
SOURCE_STORE: ImmutableSourceStore
ARCHIVE_STORE: CategorizedArchiveStore
BASIS_WORKSPACE: LocalBasisWorkspace
AUTH_STORE: LocalAuthStore
SESSIONS: dict[str, dict[str, Any]] = {}


def _configure_deployment(config: DeploymentConfig) -> None:
    """Bind all adapter-owned stores to one deployment data root."""

    global DEPLOYMENT_CONFIG, DEPLOYMENT_STORAGE, PROJECT_WORKSPACE, SOURCE_STORE, ARCHIVE_STORE, BASIS_WORKSPACE, AUTH_STORE
    config.ensure_layout()
    DEPLOYMENT_CONFIG = config
    DEPLOYMENT_STORAGE = DeploymentStorageAdapter(config)
    PROJECT_WORKSPACE = LocalProjectWorkspace(config.roots.projects, storage_adapter=DEPLOYMENT_STORAGE)
    SOURCE_STORE = ImmutableSourceStore(config.roots.sources)
    ARCHIVE_STORE = CategorizedArchiveStore(config.roots.archive)
    BASIS_WORKSPACE = LocalBasisWorkspace(config.roots.basis)
    AUTH_STORE = LocalAuthStore(config.roots.auth)


_configure_deployment(DeploymentConfig.from_environment())

RISK_META = {
    "block": {"level": "critical", "label": "紧急阻断", "color": "red", "priority": 3},
    "warn": {"level": "warning", "label": "预警", "color": "yellow", "priority": 2},
    "info": {"level": "notice", "label": "提示", "color": "blue", "priority": 1},
}

DASHBOARD_LIMITS = {
    "warn_rate": Decimal("0.03"),
    "critical_rate": Decimal("0.10"),
}

ARCHITECTURE: dict[str, Any] = {
    "layers": [
        {
            "id": "gui",
            "label": "GUI",
            "status": "active",
            "description": "只编排请求、呈现运行状态与证据，不复制业务规则。",
        },
        {
            "id": "gateway",
            "label": "CapabilityGateway",
            "status": "active",
            "description": "唯一执行边界，接受 P01–P09；P09 只读派生成果经营视图。",
        },
        {
            "id": "plugins",
            "label": "Plugins",
            "status": "active",
            "description": "业务能力实现与声明式占位能力。",
        },
        {
            "id": "adapters",
            "label": "Adapters",
            "status": "boundary",
            "description": "业务适配器、部署与存储适配，不改变 Core。",
        },
        {
            "id": "deployment",
            "label": "Deployment / Storage",
            "status": "active",
            "description": "统一服务节点、项目数据根目录、并发写入锁和备份边界；终端不直接改底座文件。",
        },
        {
            "id": "core",
            "label": "Core",
            "status": "active",
            "description": "不可变记录、运行时、来源哈希与证据模型。",
        },
        {
            "id": "evidence",
            "label": "Evidence",
            "status": "output",
            "description": "保留 project/source 标识和不可变审查依据。",
        },
    ],
    "capabilities": [
        {"id": "P01", "label": "合同与招采依据 intake", "status": "implemented", "surface": "合同与招采依据台"},
        {"id": "P02", "label": "工程量清单 intake", "status": "implemented", "surface": "清单输入"},
        {"id": "P03", "label": "图纸 intake", "status": "implemented", "surface": "图纸登记台"},
        {"id": "P04", "label": "基线台账", "status": "implemented", "surface": "零号台账"},
        {"id": "P05", "label": "成本计划", "status": "implemented", "surface": "成本计划"},
        {"id": "P06", "label": "变更管理", "status": "implemented", "surface": "变更工作台"},
        {"id": "P07", "label": "证据关联", "status": "implemented", "surface": "证据链"},
        {"id": "P08", "label": "结算初审", "status": "implemented", "surface": "当前工作面"},
        {"id": "P09", "label": "全过程成果经营", "status": "implemented", "surface": "成果经营台"},
    ],
    "shared_modules": [
        {"label": "plugins/normalize.py", "description": "单位归一化与换算，纯 helper，不注册 Gateway。"},
        {"label": "plugins/basis.py", "description": "价格口径可比性，冲突时不输出偏差数。"},
    ],
    "invariants": [
        "Core 不反向依赖业务插件或外部适配器。",
        "GUI / adapters / plugins → Core。",
        "P01–P08 保存专业事实，P09 只读派生经营结果；不建立第二金额事实源。",
    ],
}

DEMO_REQUEST: dict[str, Any] = {
    "project_id": "demo-road-2026",
    "source_id": "sanitized-boq",
    "project_name": "演示道路项目",
    "source_name": "示例清单资料",
    "rows": [
        {
            "row": 4,
            "code": "040202002001",
            "name": "石灰稳定土",
            "unit": "m3",
            "quantity": "880",
            "price": "128.60",
            "total": "113000.00",
        },
        {
            "row": 5,
            "code": "040203006001",
            "name": "沥青混凝土面层",
            "unit": "m3",
            "quantity": "12600",
            "price": "96.40",
            "total": "1214640.00",
        },
    ],
    "reference_units": {
        "040202002001": "m3",
        "040203006001": "m2",
    },
    "subject_basis": {
        "tax_inclusion": "tax_exclusive",
        "price_type": "winning_bid",
        "source": "HT-2026-001",
        "price_date": "2026-01",
    },
    "reference_basis": {
        "tax_inclusion": "tax_inclusive",
        "price_type": "market_quote",
        "source": "quote-2026-07",
        "price_date": "2026-07",
    },
    "reference_prices": {
        "040202002001": "121.00",
        "040203006001": "103.20",
    },
    "boq_rows": [
        ["项目编码", "项目名称", "计量单位", "工程量"],
        ["040202002001", "石灰稳定土", "m3", 880],
        ["040203006001", "沥青混凝土面层", "m2", 12600],
    ],
    "contract_prices": {
        "040202002001": "128.60",
        "040203006001": "96.40",
    },
    "market_prices": {
        "040202002001": "121.00",
        "040203006001": "103.20",
    },
    "contract_basis": {
        "tax_inclusion": "tax_exclusive",
        "price_type": "winning_bid",
        "source": "HT-2026-001",
        "price_date": "2026-01",
    },
    "market_basis": {
        "tax_inclusion": "tax_exclusive",
        "price_type": "market_quote",
        "source": "quote-2026-07",
        "price_date": "2026-07",
    },
}


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        default=_json_default,
        separators=(",", ":"),
    ).encode("utf-8")


def _optional_actor(headers: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    if not headers:
        return None
    raw = headers.get("Authorization", "")
    token = raw.removeprefix("Bearer ").strip()
    actor = SESSIONS.get(token)
    if actor is None:
        return None
    # Rehydrate the public record on each request so a project-manager grant
    # or revoke takes effect for an already-open delegated admin session.
    refreshed = AUTH_STORE.public_user_by_id(str(actor.get("id", "")))
    if refreshed is None:
        SESSIONS.pop(token, None)
        return None
    SESSIONS[token] = refreshed
    return refreshed


def _require_actor(headers: Mapping[str, str], permission: str | None = None) -> dict[str, Any]:
    actor = _optional_actor(headers)
    if actor is None:
        raise PermissionError("请先登录后再进行此操作")
    if permission and permission not in set(actor.get("permissions", [])):
        raise PermissionError(f"当前角色没有“{permission}”权限")
    return actor


_COST_DETAIL_KEYS = {
    "amount",
    "contract_amount",
    "contract_subtotal",
    "contract_unit_price",
    "market_amount",
    "market_total",
    "market_unit_price",
    "net_amount",
    "over_limit_amount",
    "over_limit_rate",
    "total_variance",
    "unit_price",
    "variance_amount",
    "zero_ledger_total",
    "baseline_cost",
    "forecast_cost",
    "estimated_revenue",
    "submitted_amount",
    "approved_measurement",
    "audit_1",
    "audit_2",
    "final_certified",
    "cash_collected",
    "expected_profit",
    "incremental_cost",
    "risk_cost",
    "physical",
    "evidence_ready",
    "submitted",
    "confirmed",
    "revenue",
    "settled",
    "paid",
    "value",
    "total",
    "total_amount",
    "physical_total",
    "evidence_ready_total",
    "submitted_total",
    "confirmed_total",
    "revenue_total",
    "settled_total",
    "paid_total",
    "value_leak_total",
    "priority_score",
}


def _can(actor: Mapping[str, Any] | None, permission: str) -> bool:
    return permission in set((actor or {}).get("permissions", []))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _redact_sensitive(value: Any, actor: Mapping[str, Any] | None) -> Any:
    """Keep operational records usable while removing sensitive cost details."""
    if _can(actor, "view_cost_detail"):
        return copy.deepcopy(value)
    if isinstance(value, Mapping):
        return {
            str(key): (None if str(key) in _COST_DETAIL_KEYS else _redact_sensitive(item, actor))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(item, actor) for item in value]
    return copy.deepcopy(value)


_ROLE_WORKSPACE_VIEWS: dict[str, set[str]] = {
    "project_manager": {"overview", "dashboard", "search", "events", "p09", "coordination", "personnel"},
    "cost_manager": {"overview", "search", "contract", "boq", "drawings", "baseline", "plan", "changes", "events", "evidence", "review", "p09", "coordination", "basis", "dashboard", "control"},
    "cost_estimator": {"overview", "search", "contract", "boq", "baseline", "plan", "changes", "events", "evidence", "coordination", "basis"},
    # Operational roles stay on their own work surfaces.  Cross-project
    # search is intentionally reserved for management/cost roles and the
    # document controller; field and material roles use their assigned P01–P08
    # surfaces, Core events, evidence, and coordination only.
    "technical_lead": {"overview", "drawings", "changes", "events", "evidence", "coordination"},
    "production_manager": {"overview", "drawings", "changes", "events", "evidence", "coordination", "dashboard"},
    "site_engineer": {"overview", "drawings", "events", "evidence", "coordination"},
    "surveyor": {"overview", "drawings", "events", "evidence", "coordination"},
    "quality_officer": {"overview", "drawings", "events", "evidence", "coordination"},
    "lab_testing_officer": {"overview", "boq", "drawings", "events", "evidence", "coordination"},
    "document_controller": {"overview", "search", "contract", "drawings", "evidence", "coordination"},
    "safety_officer": {"overview", "drawings", "changes", "events", "evidence", "coordination"},
    "procurement_officer": {"overview", "contract", "boq", "events", "evidence", "coordination"},
    "warehouse_officer": {"overview", "boq", "events", "evidence", "coordination"},
    "administrative_officer": {"overview", "coordination", "personnel"},
}

_WORKSPACE_KEY_VIEWS = {
    "contract": "contract",
    "boq": "boq",
    "drawings": "drawings",
    "baseline": "baseline",
    "cost_plan": "plan",
    "changes": "changes",
    "evidence": "evidence",
    "review": "review",
    "events": "events",
    "collaboration": "coordination",
    "basis_references": "basis",
}

_CAPABILITY_ROLE_ACCESS: dict[str, set[str]] = {
    "contract": {"cost_manager", "cost_estimator", "procurement_officer", "document_controller"},
    "boq": {"cost_manager", "cost_estimator", "procurement_officer", "warehouse_officer", "lab_testing_officer"},
    "drawings": {"cost_manager", "technical_lead", "production_manager", "site_engineer", "surveyor", "quality_officer", "lab_testing_officer", "document_controller", "safety_officer"},
    # P04 零号台账 is the commercial opening baseline.  Only its two cost
    # roles may enter or modify it; other roles receive derived references.
    "baseline": {"cost_manager", "cost_estimator"},
    "cost-plan": {"cost_manager", "cost_estimator"},
    "changes": {"cost_manager", "cost_estimator", "technical_lead", "production_manager", "site_engineer", "safety_officer"},
    "evidence": {"cost_manager", "cost_estimator", "technical_lead", "production_manager", "site_engineer", "surveyor", "quality_officer", "lab_testing_officer", "document_controller", "safety_officer", "procurement_officer", "warehouse_officer"},
    "review": {"cost_manager"},
    "p09": {"project_manager", "cost_manager"},
    "search": {"project_manager", "cost_manager", "cost_estimator", "document_controller"},
}


def _actor_roles(actor: Mapping[str, Any]) -> set[str]:
    roles = actor.get("roles")
    if isinstance(roles, list) and roles:
        return {str(role) for role in roles if str(role).strip()}
    role = str(actor.get("role", "")).strip()
    return {role} if role else set()


def _workspace_views_for_actor(actor: Mapping[str, Any]) -> set[str]:
    views: set[str] = set()
    for role in _actor_roles(actor):
        views.update(_ROLE_WORKSPACE_VIEWS.get(role, {"overview", "search", "events", "coordination"}))
    if _can(actor, "manage_personnel"):
        views.add("personnel")
    if not _can(actor, "view_cost_detail"):
        views.discard("control")
    return views


def _require_capability_role(actor: Mapping[str, Any], capability: str) -> None:
    roles = _actor_roles(actor)
    allowed = _CAPABILITY_ROLE_ACCESS.get(capability, set())
    if not roles.intersection(allowed):
        raise PermissionError(f"当前岗位不能访问或写入 {capability} 工作面")


def _visible_workspace(state: dict[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    if (actor or {}).get("role") == ROLE_PROJECT_MANAGER:
        return {
            "project": copy.deepcopy(state.get("project") or {}),
            "sources": [],
            "access": "kpi_only",
            "role_description": "仅显示项目重要指标、风险预警与经营趋势",
            "visible_views": sorted(_workspace_views_for_actor(actor)),
        }
    visible = _redact_sensitive(state, actor)
    allowed_views = _workspace_views_for_actor(actor)
    for key, view in _WORKSPACE_KEY_VIEWS.items():
        if view not in allowed_views:
            visible.pop(key, None)
    if "basis" not in allowed_views:
        visible["basis_references"] = []
    if "sources" not in allowed_views and not _can(actor, "view_source"):
        visible["sources"] = []
    visible["access"] = "full" if _can(actor, "view_cost_detail") else "operational_redacted"
    visible["role_description"] = "完整成本明细" if _can(actor, "view_cost_detail") else "本岗位工作面可见，其他专业成果按岗位边界隐藏"
    visible["visible_views"] = sorted(allowed_views)
    return visible


def _risk_for(severity: str) -> dict[str, Any]:
    return dict(RISK_META.get(severity, RISK_META["info"]))


def _decorate_risk(result: dict[str, Any]) -> dict[str, Any]:
    findings = []
    highest = RISK_META["info"]
    for raw in result.get("findings", []):
        finding = dict(raw)
        risk = _risk_for(str(finding.get("severity", "info")))
        finding["risk"] = risk
        if risk["priority"] > highest["priority"]:
            highest = risk
        findings.append(finding)
    result["findings"] = findings
    result["risk"] = dict(highest if findings else {**RISK_META["info"], "label": "无风险事项"})
    return result


def _review(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("rows must be a JSON array")
    context = {
        key: payload[key]
        for key in (
            "project_id",
            "source_id",
            "rows",
            "reference_units",
            "reference_prices",
            "reference_basis",
            "subject_basis",
            "quantity_ceilings",
            "expected_divisions",
            "price_deviation_threshold",
            "unit_aliases",
        )
        if key in payload
    }
    result = _decorate_risk(dict(RUNTIME.gateway.execute("P08", context)))
    PROJECT_WORKSPACE.set_stage(str(context.get("project_id", "")), "review", result)
    PROJECT_WORKSPACE.record_alert_snapshot(
        str(context.get("project_id", "")),
        result,
        str(context.get("source_id", "")),
    )
    if actor and context.get("project_id"):
        PROJECT_WORKSPACE.append_audit(
            str(context["project_id"]),
            "review.run",
            actor,
            str(context.get("source_id", "")),
            {"risk": result.get("risk"), "finding_count": result.get("summary", {}).get("finding_count", 0)},
        )
    return result


def _boq(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("rows must be a JSON array")
    mode = payload.get("mode", "standard")
    if mode != "standard":
        raise ValueError("WebUI P02 entry currently accepts standard table rows only")
    context = {
        key: payload[key]
        for key in ("project_id", "source_id", "rows", "mode")
        if key in payload
    }
    result = dict(RUNTIME.gateway.execute("P02", context))
    PROJECT_WORKSPACE.set_stage(str(context.get("project_id", "")), "boq", result)
    if actor and context.get("project_id"):
        PROJECT_WORKSPACE.append_audit(
            str(context["project_id"]),
            "boq.modified",
            actor,
            str(context.get("source_id", "")),
            {"item_count": result.get("item_count", 0)},
        )
    return result


def _multipart_fields(content_type: str, body: bytes) -> dict[str, tuple[str, bytes]]:
    """Read the small multipart envelope used by the local file intake form."""
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, re.IGNORECASE)
    if not match:
        raise ValueError("资料上传缺少 multipart 边界")
    boundary = (match.group(1) or match.group(2)).strip().encode("utf-8")
    delimiter = b"--" + boundary
    fields: dict[str, tuple[str, bytes]] = {}
    for raw_part in body.split(delimiter)[1:]:
        if raw_part.startswith(b"--"):
            continue
        raw_part = raw_part.strip(b"\r\n")
        if b"\r\n\r\n" not in raw_part:
            continue
        header_bytes, content = raw_part.split(b"\r\n\r\n", 1)
        disposition = next(
            (line for line in header_bytes.split(b"\r\n") if line.lower().startswith(b"content-disposition:")),
            b"",
        ).decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        filename_star_match = re.search(r"filename\*=UTF-8''([^;\r\n]+)", disposition, re.IGNORECASE)
        filename = (
            unquote(filename_star_match.group(1))
            if filename_star_match
            else filename_match.group(1) if filename_match else ""
        )
        content = content.rstrip(b"\r\n")
        name = name_match.group(1)
        fields[name] = (filename, content)
    return fields


def _normalize_archive_category(archive_category: str) -> str:
    category = str(archive_category or "").strip("/\\ ")
    return category[:-2] if category.endswith("资料资料") else category


def _archive_path(archive_area: str, archive_category: str, filename: str) -> str:
    """Build a logical archive path without duplicating same-named area folders."""
    area_parts = [part.strip("/\\ ") for part in str(archive_area).split("/") if part.strip("/\\ ")]
    category = _normalize_archive_category(archive_category)
    if category and (not area_parts or area_parts[-1] != category):
        area_parts.append(category)
    area_parts.append(str(filename).strip("/\\ "))
    return "/".join(part for part in area_parts if part)


def _boq_upload(
    content_type: str,
    body: bytes,
    actor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("资料上传需要 multipart/form-data")
    fields = _multipart_fields(content_type, body)
    project_id = fields.get("project_id", ("", b""))[1].decode("utf-8").strip()
    source_id = fields.get("source_id", ("", b""))[1].decode("utf-8").strip()
    archive_area = fields.get("archive_area", ("", b""))[1].decode("utf-8").strip() or "清单与计价资料"
    archive_category = _normalize_archive_category(fields.get("archive_category", ("", b""))[1].decode("utf-8").strip())
    recognize_requested = fields.get("recognize", ("", b""))[1].decode("utf-8").strip().lower() not in {"0", "false", "no", "off"}
    filename, content = fields.get("file", ("", b""))
    if not project_id or not source_id:
        raise ValueError("资料上传缺少项目或资料标识")
    if not content:
        raise ValueError("请选择清单资料文件")

    suffix = Path(filename).suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        context: dict[str, Any] = {
            "project_id": project_id,
            "source_id": source_id,
            "boq_bytes": content,
            "mode": "standard",
        }
    elif suffix in {".csv", ".txt"}:
        text = content.decode("utf-8-sig", errors="strict")
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except csv.Error as exc:
            raise ValueError(f"无法读取清单资料：{exc}") from exc
        context = {"project_id": project_id, "source_id": source_id, "rows": rows}
    else:
        raise ValueError("仅支持 .xlsx、.xlsm 或 .csv 清单资料")
    result = dict(RUNTIME.gateway.execute("P02", context))
    source = SOURCE_STORE.ingest(filename, content, mimetypes.guess_type(filename)[0] or "application/octet-stream")
    archive_storage_path = str(
        ARCHIVE_STORE.materialize(
            project_id,
            archive_area,
            archive_category,
            filename,
            SOURCE_STORE.path_for(source),
            source.content_hash,
        )
    )
    PROJECT_WORKSPACE.add_source(
        project_id,
        {
            "source_id": source_id,
            "document_id": source.id,
            "name": filename,
            "kind": "清单资料",
            "media_type": source.media_type,
            "content_hash": source.content_hash,
            "storage_path": str(SOURCE_STORE.path_for(source)),
            "archive_storage_path": archive_storage_path,
            "archive_area": archive_area,
            "archive_path": _archive_path(archive_area, archive_category, filename),
            "archive_category": archive_category,
            "size": len(content),
        },
    )
    source_metadata = PROJECT_WORKSPACE.load(project_id)["sources"][-1]
    if recognize_requested:
        source_metadata, _ = _auto_recognize_source(project_id, source_metadata)
    PROJECT_WORKSPACE.set_stage(project_id, "boq", result)
    if actor:
        PROJECT_WORKSPACE.append_audit(
            project_id,
            "source.uploaded",
            actor,
            source_id,
            {"name": filename, "kind": "清单资料", "item_count": result.get("item_count", 0)},
        )
    return {
        **result,
        "source": source_metadata,
        "archive": {
            "area": source_metadata.get("archive_area", archive_area),
            "path": source_metadata.get("archive_path", _archive_path(archive_area, archive_category, filename)),
            "archive_storage_path": source_metadata.get("archive_storage_path", ""),
            "storage_path": source_metadata.get("storage_path", ""),
        },
    }


def _cost_plan(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("items must be a JSON array")
    for key in ("contract_prices", "market_prices", "contract_basis", "market_basis"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], dict):
            raise ValueError(f"{key} must be a JSON object")
    context = {
        key: payload[key]
        for key in (
            "project_id",
            "source_id",
            "items",
            "contract_prices",
            "market_prices",
            "contract_basis",
            "market_basis",
        )
        if key in payload
    }
    result = dict(RUNTIME.gateway.execute("P05", context))
    PROJECT_WORKSPACE.set_stage(str(context.get("project_id", "")), "cost_plan", result)
    if actor and context.get("project_id"):
        PROJECT_WORKSPACE.append_audit(
            str(context["project_id"]),
            "cost_plan.modified",
            actor,
            str(context.get("source_id", "")),
            {"item_count": len(result.get("items", []))},
        )
    return result


def _structured_capability(
    payload: object,
    capability_id: str,
    stage: str,
    action: str,
    fields: tuple[str, ...],
    actor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one structured P01/P03/P04/P06/P07 workbench stage."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    context = {
        key: payload[key]
        for key in ("project_id", "source_id", *fields)
        if key in payload
    }
    result = dict(RUNTIME.gateway.execute(capability_id, context))
    PROJECT_WORKSPACE.set_stage(str(context.get("project_id", "")), stage, result)
    if actor and context.get("project_id"):
        summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
        PROJECT_WORKSPACE.append_audit(
            str(context["project_id"]),
            action,
            actor,
            str(context.get("source_id", "")),
            {"capability_id": capability_id, **dict(summary)},
        )
    return result


def _contract(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _structured_capability(payload, "P01", "contract", "contract.modified", ("contract", "obligations"), actor)


def _drawings(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _structured_capability(payload, "P03", "drawings", "drawings.modified", ("drawings",), actor)


def _baseline(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _structured_capability(payload, "P04", "baseline", "baseline.modified", ("entries",), actor)


def _changes(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _structured_capability(payload, "P06", "changes", "changes.modified", ("changes",), actor)


def _evidence(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _structured_capability(payload, "P07", "evidence", "evidence.modified", ("links",), actor)


def _project(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not project_id or not name:
        raise ValueError("项目需要名称")
    existed = PROJECT_WORKSPACE.load(project_id) is not None
    state = PROJECT_WORKSPACE.create(project_id, name)
    if actor and not existed:
        state = PROJECT_WORKSPACE.append_audit(project_id, "project.created", actor, project_id, {"name": name})
    return state


def _source_upload(
    content_type: str,
    body: bytes,
    actor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("资料上传需要 multipart/form-data")
    fields = _multipart_fields(content_type, body)
    project_id = fields.get("project_id", ("", b""))[1].decode("utf-8").strip()
    source_id = fields.get("source_id", ("", b""))[1].decode("utf-8").strip()
    archive_area = fields.get("archive_area", ("", b""))[1].decode("utf-8").strip() or "项目资料库/待分类"
    archive_category = _normalize_archive_category(fields.get("archive_category", ("", b""))[1].decode("utf-8").strip())
    recognize_requested = fields.get("recognize", ("", b""))[1].decode("utf-8").strip().lower() not in {"0", "false", "no", "off"}
    filename, content = fields.get("file", ("", b""))
    if not project_id:
        raise ValueError("资料上传缺少项目标识")
    if not filename or not content:
        raise ValueError("请选择项目资料文件")
    source_id = source_id or Path(filename).stem
    source = SOURCE_STORE.ingest(filename, content, mimetypes.guess_type(filename)[0] or "application/octet-stream")
    archive_storage_path = str(
        ARCHIVE_STORE.materialize(
            project_id,
            archive_area,
            archive_category,
            filename,
            SOURCE_STORE.path_for(source),
            source.content_hash,
        )
    )
    suffix = Path(filename).suffix.lower()
    kind = {
        ".doc": "Word 文档",
        ".docx": "Word 文档",
        ".xlsx": "Excel 资料",
        ".xlsm": "Excel 资料",
        ".csv": "表格资料",
        ".pdf": "PDF 资料",
        ".pptx": "PowerPoint 资料",
        ".dwg": "CAD 图纸",
        ".dxf": "CAD 图纸",
        ".jpg": "图片资料",
        ".jpeg": "图片资料",
        ".png": "图片资料",
        ".bmp": "图片资料",
        ".tif": "图片资料",
        ".tiff": "图片资料",
        ".md": "文章资料",
        ".html": "文章资料",
        ".htm": "文章资料",
        ".json": "数据资料",
        ".xml": "数据资料",
        ".zip": "项目资料包",
    }.get(suffix, "项目资料")
    metadata = {
        "source_id": source_id,
        "document_id": source.id,
        "name": filename,
        "kind": kind,
        "media_type": source.media_type,
        "content_hash": source.content_hash,
        "storage_path": str(SOURCE_STORE.path_for(source)),
        "archive_storage_path": archive_storage_path,
        "archive_area": archive_area,
        "archive_path": _archive_path(archive_area, archive_category, filename),
        "archive_category": archive_category,
        "size": len(content),
    }
    state = PROJECT_WORKSPACE.add_source(project_id, metadata)
    if recognize_requested:
        metadata, state = _auto_recognize_source(project_id, metadata)
    if actor:
        state = PROJECT_WORKSPACE.append_audit(
            project_id,
            "source.uploaded",
            actor,
            source_id,
            {"name": filename, "kind": kind, "recognition": (metadata.get("recognition") or {}).get("status")},
        )
    return {"source": metadata, "workspace": state}


def _persist_recognition(
    project_id: str,
    source: dict[str, Any],
    connector_id: str = "local-auto",
    allow_external: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document = SourceDocument(
        name=str(source.get("name", "source.bin")),
        content_hash=str(source["content_hash"]),
        media_type=str(source.get("media_type", "application/octet-stream")),
    )
    content = SOURCE_STORE.read(document)
    result, artifact_content = recognize_source(
        document.name,
        content,
        connector_id=connector_id,
        allow_external=allow_external,
    )
    if artifact_content:
        artifact_name = f"{Path(document.name).stem or 'source'}.md"
        artifact = SOURCE_STORE.ingest(artifact_name, artifact_content, "text/markdown")
        result["artifact"] = {
            "name": artifact_name,
            "document_id": artifact.id,
            "content_hash": artifact.content_hash,
            "media_type": artifact.media_type,
            "storage_path": str(SOURCE_STORE.path_for(artifact)),
            "size": len(artifact_content),
        }
    updated_source = {
        **source,
        "storage_path": str(SOURCE_STORE.path_for(document.content_hash)),
        "recognition": result,
    }
    state = PROJECT_WORKSPACE.add_source(project_id, updated_source)
    return result, updated_source, state


def _auto_recognize_source(project_id: str, source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        result, updated, state = _persist_recognition(project_id, source)
    except (FileNotFoundError, KeyError, RecognitionError, ValueError) as exc:
        result = {
            "status": "unavailable",
            "mode": "local",
            "connector_id": "local-auto",
            "category": "项目资料",
            "tags": [],
            "confidence": 0.0,
            "text_length": 0,
            "text_preview": "",
            "message": f"本地识别未完成：{exc}",
        }
        updated = {**source, "recognition": result}
        state = PROJECT_WORKSPACE.add_source(project_id, updated)
    return updated, state


def _recognize_source(payload: object, actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip()
    source_id = str(payload.get("source_id", "")).strip()
    connector_id = str(payload.get("connector_id", "local-auto")).strip() or "local-auto"
    allow_external = payload.get("allow_external") is True
    if not project_id or not source_id:
        raise ValueError("识别请求缺少项目或资料标识")
    state = _workspace(project_id)
    source = next((item for item in state.get("sources", []) if item.get("source_id") == source_id), None)
    if source is None:
        raise FileNotFoundError("项目资料不存在")
    result, updated_source, updated_state = _persist_recognition(
        project_id,
        dict(source),
        connector_id=connector_id,
        allow_external=allow_external,
    )
    if result.get("status") == "consent_required":
        return {"recognition": result, "source": source, "workspace": state}
    if actor:
        updated_state = PROJECT_WORKSPACE.append_audit(
            project_id,
            "source.recognized",
            actor,
            source_id,
            {"connector_id": connector_id, "status": result.get("status"), "mode": result.get("mode")},
        )
        return {"recognition": result, "source": updated_source, "workspace": updated_state}
    return {"recognition": result, "source": updated_source, "workspace": updated_state}


def _auth_register(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user = AUTH_STORE.register(
        str(payload.get("username", "")),
        str(payload.get("password", "")),
        str(payload.get("role", "")),
        payload.get("roles") if isinstance(payload.get("roles"), list) else None,
    )
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = user
    return {"token": token, "user": user}


def _auth_login(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user = AUTH_STORE.authenticate(str(payload.get("username", "")), str(payload.get("password", "")))
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = user
    return {"token": token, "user": user}


def _personnel_create(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip() or None
    username = str(payload.get("username", payload.get("name", ""))).strip()
    role = str(payload.get("role", "")).strip()
    raw_password = payload.get("password")
    password = str(raw_password).strip() if raw_password is not None else ""
    temporary_password = ""
    if not password:
        # Managed personnel are entered by the project manager or an
        # authorized administrative officer.  Keep the login credential
        # secure while removing the need for the manager to invent a
        # password: the one-time value is returned only in this response.
        temporary_password = f"BC-{secrets.token_urlsafe(9)}"
        password = temporary_password
    user = AUTH_STORE.register(
        username,
        password,
        role,
    )
    if project_id:
        AUTH_STORE.add_user_to_project(project_id, str(user["id"]))
    AUTH_STORE.record_personnel_audit(
        dict(actor),
        "personnel.created",
        str(user["id"]),
        {"username": user["username"], "role": user["role"], "project_id": project_id or ""},
        project_id=project_id,
    )
    snapshot = AUTH_STORE.personnel_snapshot(project_id)
    if temporary_password:
        snapshot["temporary_credentials"] = {
            "username": user["username"],
            "password": temporary_password,
            "role": user["role"],
            "role_label": user["role_label"],
            "notice": "请将此初始密码安全交给本人；刷新人员管理后不再显示。",
        }
    return snapshot


def _personnel_authorize(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        raise ValueError("缺少目标人员")
    authorized = bool(payload.get("authorized", True))
    project_id = str(payload.get("project_id", "")).strip() or None
    return AUTH_STORE.authorize_personnel_admin(dict(actor), user_id, authorized, project_id=project_id)


def _personnel_delete(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        raise ValueError("缺少目标人员")
    project_id = str(payload.get("project_id", "")).strip() or None
    return AUTH_STORE.delete_user(dict(actor), user_id, project_id=project_id)


def _personnel_rename(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user_id = str(payload.get("user_id", "")).strip()
    new_username = str(payload.get("new_username", payload.get("username", ""))).strip()
    if not user_id or not new_username:
        raise ValueError("缺少目标人员或新姓名")
    project_id = str(payload.get("project_id", "")).strip() or None
    return AUTH_STORE.rename_user(dict(actor), user_id, new_username, project_id=project_id)


def _personnel_roles(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    user_id = str(payload.get("user_id", "")).strip()
    roles = payload.get("roles")
    if not user_id or not isinstance(roles, list):
        raise ValueError("缺少目标人员或岗位组合")
    project_id = str(payload.get("project_id", "")).strip() or None
    return AUTH_STORE.update_roles(dict(actor), user_id, roles, project_id=project_id)


def _source_for(state: dict[str, Any], source_id: str) -> dict[str, Any]:
    source = next((item for item in state.get("sources", []) if item.get("source_id") == source_id), None)
    if source is None:
        raise FileNotFoundError("项目资料不存在")
    return source


def _source_view(project_id: str, source_id: str, derived: bool, actor: Mapping[str, Any]) -> tuple[bytes, str, str]:
    state = _workspace(project_id)
    source = _source_for(state, source_id)
    selected = source
    if derived:
        selected = dict((source.get("recognition") or {}).get("artifact") or {})
        if not selected:
            raise FileNotFoundError("该资料没有本地识别副本")
    document = SourceDocument(
        name=str(selected.get("name", source.get("name", "source.bin"))),
        content_hash=str(selected.get("content_hash", source.get("content_hash", ""))),
        media_type=str(selected.get("media_type", source.get("media_type", "application/octet-stream"))),
    )
    content = SOURCE_STORE.read(document)
    PROJECT_WORKSPACE.append_audit(
        project_id,
        "source.viewed",
        actor,
        source_id,
        {"derived": derived, "name": document.name},
    )
    content_type = document.media_type
    if document.name.lower().endswith((".md", ".html", ".htm")):
        content_type = "text/plain; charset=utf-8"
    return content, content_type, Path(document.name).name


def _basis_public(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return business-facing basis metadata without raw hashes or backend IDs."""
    visible = dict(item)
    visible.pop("content_hash", None)
    visible.pop("document_id", None)
    visible.pop("source_id", None)
    recognition = dict(visible.get("recognition") or {})
    recognition.pop("text_preview", None)
    if recognition.get("artifact"):
        artifact = recognition["artifact"]
        recognition["artifact"] = {key: artifact.get(key) for key in ("name", "media_type", "storage_path", "size")}
    visible["recognition"] = recognition
    return visible


def _basis_upload(content_type: str, body: bytes, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("外部依据上传需要 multipart/form-data")
    fields = _multipart_fields(content_type, body)
    filename, content = fields.get("file", ("", b""))
    if not filename or not content:
        raise ValueError("请选择政策、定额、信息价或市场价文件")
    category = fields.get("category", ("", b""))[1].decode("utf-8").strip() or "policy"
    category_meta = next((item for item in BASIS_CATEGORIES if item["id"] == category), None)
    if category_meta is None:
        raise ValueError("请选择有效的外部依据分类")
    source = SOURCE_STORE.ingest(filename, content, mimetypes.guess_type(filename)[0] or "application/octet-stream")
    try:
        recognition, artifact_content = recognize_source(filename, content)
    except (RecognitionError, ValueError) as exc:
        recognition = {
            "status": "unavailable",
            "mode": "local",
            "connector_id": "local-auto",
            "category": category_meta["label"],
            "tags": [],
            "confidence": 0.0,
            "text_length": 0,
            "text_preview": "",
            "message": f"本地识别未完成：{exc}",
        }
        artifact_content = None
    artifact = None
    if artifact_content:
        artifact_name = f"{Path(filename).stem or 'basis'}.md"
        derived = SOURCE_STORE.ingest(artifact_name, artifact_content, "text/markdown")
        artifact = {
            "name": artifact_name,
            "document_id": derived.id,
            "content_hash": derived.content_hash,
            "media_type": derived.media_type,
            "storage_path": str(SOURCE_STORE.path_for(derived)),
            "size": len(artifact_content),
        }
        recognition["artifact"] = artifact
    def field(name: str) -> str:
        return fields.get(name, ("", b""))[1].decode("utf-8").strip()
    item = {
        "basis_id": f"basis-{category}-{source.content_hash[:12]}",
        "name": filename,
        "title": field("title") or Path(filename).stem,
        "category": category,
        "category_label": category_meta["label"],
        "description": field("description"),
        "source_org": field("source_org"),
        "source_url": field("source_url"),
        "published_at": field("published_at"),
        "effective_from": field("effective_from"),
        "effective_to": field("effective_to"),
        "region": field("region"),
        "tax_mode": field("tax_mode"),
        "pricing_mode": field("pricing_mode"),
        "version": field("version"),
        "archive_area": "外部依据库",
        "archive_path": f"外部依据库/{category_meta['label']}/{filename}",
        "storage_path": str(SOURCE_STORE.path_for(source)),
        "media_type": source.media_type,
        "content_hash": source.content_hash,
        "document_id": source.id,
        "size": len(content),
        "recognition": recognition,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": {key: actor.get(key, "") for key in ("id", "username", "role", "role_label")},
    }
    saved = BASIS_WORKSPACE.add(item)
    return {"basis": _basis_public(saved), "items": [_basis_public(row) for row in BASIS_WORKSPACE.list()]}


def _basis_reference(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip()
    basis_id = str(payload.get("basis_id", "")).strip()
    stage = str(payload.get("stage", "")).strip().upper()
    if not project_id or not basis_id or stage not in {"P04", "P05", "P08"}:
        raise ValueError("依据引用需要项目、依据和 P04/P05/P08 工作阶段")
    basis = BASIS_WORKSPACE.get(basis_id)
    if basis is None:
        raise FileNotFoundError("外部依据不存在")
    state = PROJECT_WORKSPACE.add_basis_reference(project_id, basis, stage)
    PROJECT_WORKSPACE.append_audit(
        project_id,
        "basis.referenced",
        actor,
        basis_id,
        {"stage": stage, "version": basis.get("version"), "content_hash": basis.get("content_hash")},
    )
    return {"basis": _basis_public(basis), "workspace": state}


def _basis_view(basis_id: str, derived: bool = False) -> tuple[bytes, str, str]:
    basis = BASIS_WORKSPACE.get(basis_id)
    if basis is None:
        raise FileNotFoundError("外部依据不存在")
    selected = dict(basis)
    if derived:
        selected = dict((basis.get("recognition") or {}).get("artifact") or {})
        if not selected:
            raise FileNotFoundError("该依据还没有本地识别稿")
    document = SourceDocument(
        name=str(selected.get("name", basis.get("name", "basis.bin"))),
        content_hash=str(selected.get("content_hash", basis.get("content_hash", ""))),
        media_type=str(selected.get("media_type", basis.get("media_type", "application/octet-stream"))),
    )
    content = SOURCE_STORE.read(document)
    content_type = "text/plain; charset=utf-8" if document.name.lower().endswith((".md", ".html", ".htm")) else document.media_type
    return content, content_type, Path(document.name).name


def _source_modify(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip()
    source_id = str(payload.get("source_id", "")).strip()
    changes = payload.get("changes")
    if not project_id or not source_id or not isinstance(changes, dict):
        raise ValueError("资料修改请求不完整")
    state = PROJECT_WORKSPACE.modify_source(project_id, source_id, changes, actor)
    return {"source": _source_for(state, source_id), "workspace": state}


def _source_delete(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    project_id = str(payload.get("project_id", "")).strip()
    source_id = str(payload.get("source_id", "")).strip()
    if not project_id or not source_id:
        raise ValueError("资料删除请求不完整")
    state = PROJECT_WORKSPACE.soft_delete_source(project_id, source_id, actor)
    return {"source": _source_for(state, source_id), "workspace": state}


def _workspace(project_id: str) -> dict[str, Any]:
    state = PROJECT_WORKSPACE.load(project_id)
    if state is None:
        raise FileNotFoundError("项目尚未建立")
    state.setdefault("basis_references", [])
    state.setdefault("events", [])
    state.setdefault("event_distillation", None)
    state.setdefault("line_adaptations", [])
    state.setdefault("collaboration", {"tasks": [], "decisions": []})
    state.setdefault("relationships", [])
    state.setdefault("golden_scenario", None)
    collaboration = state.get("collaboration")
    if not isinstance(collaboration, dict):
        state["collaboration"] = {"tasks": [], "decisions": []}
    else:
        collaboration.setdefault("tasks", [])
        collaboration.setdefault("decisions", [])
    changed = False
    # Migrate events created before the Outcome projection was introduced.
    migrated_events = []
    for raw_event in state.get("events") or []:
        if not isinstance(raw_event, Mapping):
            continue
        migrated = ensure_outcome_track(raw_event)
        migrated_events.append(migrated)
        if migrated != raw_event:
            changed = True
    if len(migrated_events) != len(state.get("events") or []):
        changed = True
    state["events"] = migrated_events
    for source in state.get("sources", []):
        archive_area = str(source.get("archive_area") or "").strip()
        archive_category = _normalize_archive_category(str(source.get("archive_category") or ""))
        if archive_category and source.get("archive_category") != archive_category:
            source["archive_category"] = archive_category
            changed = True
        if archive_area and source.get("name"):
            expected_archive_path = _archive_path(archive_area, archive_category, str(source["name"]))
            if source.get("archive_path") != expected_archive_path:
                source["archive_path"] = expected_archive_path
                changed = True
        content_hash = source.get("content_hash")
        if content_hash and not source.get("storage_path"):
            source["storage_path"] = str(SOURCE_STORE.path_for(str(content_hash)))
            changed = True
        if content_hash and archive_area and source.get("name"):
            source_path = SOURCE_STORE.path_for(str(content_hash))
            if source_path.is_file():
                archive_storage_path = str(
                    ARCHIVE_STORE.materialize(
                        project_id,
                        archive_area,
                        archive_category,
                        str(source["name"]),
                        source_path,
                        str(content_hash),
                    )
                )
                if source.get("archive_storage_path") != archive_storage_path:
                    source["archive_storage_path"] = archive_storage_path
                    changed = True
        artifact = (source.get("recognition") or {}).get("artifact") or {}
        artifact_hash = artifact.get("content_hash")
        if artifact_hash and not artifact.get("storage_path"):
            artifact["storage_path"] = str(SOURCE_STORE.path_for(str(artifact_hash)))
            changed = True
    if changed:
        state = PROJECT_WORKSPACE.save(state)
    return state


def _event_public(event: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    """Expose business-readable event data while keeping role boundaries."""
    vector = build_state_vector(event)
    alerts = evaluate_event_rules(event)
    if (actor or {}).get("role") == ROLE_PROJECT_MANAGER:
        identity = event.get("identity") if isinstance(event.get("identity"), Mapping) else {}
        classification = event.get("classification") if isinstance(event.get("classification"), Mapping) else {}
        return {
            "event_id": event.get("event_id", ""),
            "project_id": event.get("project_id", ""),
            "title": identity.get("title", ""),
            "summary": identity.get("summary", ""),
            "event_type": classification.get("event_type", ""),
            "severity": classification.get("severity", ""),
            "state_vector": vector,
            "alerts": alerts,
            "status_history_count": len((_mapping(event.get("governance")).get("status_history") or [])),
        }
    visible = _redact_sensitive(dict(event), actor)
    visible["state_vector"] = vector
    visible["alerts"] = alerts
    return visible


def _event_kernel_response(state: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = state.get("event_distillation")
    if (actor or {}).get("role") == ROLE_PROJECT_MANAGER:
        visible_snapshot = None
        if isinstance(snapshot, Mapping):
            summary = dict(snapshot.get("summary") or {})
            visible_snapshot = {"summary": summary, "updated_at": snapshot.get("updated_at"), "local_only": True}
    else:
        visible_snapshot = _redact_sensitive(snapshot, actor) if isinstance(snapshot, Mapping) else None
    return {
        "project": dict(state.get("project") or {}),
        "events": [_event_public(event, actor) for event in state.get("events") or [] if isinstance(event, Mapping)],
        "distillation": visible_snapshot,
        "catalog": {
            "statuses": list(EVENT_STATUSES),
            "source_types": list(EVENT_SOURCE_TYPES),
            "event_types": list(EVENT_TYPES),
            "severities": list(SEVERITIES),
            "dimensions": list(DIMENSIONS),
            "outcome_statuses": list(OUTCOME_STATUSES),
            "outcome_types": list(OUTCOME_TYPES),
            "outcome_transitions": {key: sorted(value) for key, value in OUTCOME_ALLOWED_TRANSITIONS.items()},
        },
        "privacy": {"local_only": True, "external_sent": False},
    }


def _event_input_mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _create_engineering_event(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("工程事件请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    if not project_id:
        raise ValueError("工程事件缺少项目标识")
    source_refs = payload.get("source_refs") or []
    if isinstance(source_refs, str):
        source_refs = [item.strip() for item in source_refs.split(",") if item.strip()]
    event = new_event(
        project_id,
        event_id=PROJECT_WORKSPACE.next_event_id(project_id),
        title=str(payload.get("title", "")),
        summary=str(payload.get("summary", "")),
        source_type=str(payload.get("source_type", "SITE_DISCOVERY")),
        event_type=str(payload.get("event_type", "SITE_CONDITION")),
        severity=str(payload.get("severity", "MEDIUM")),
        discovered_by=str(payload.get("discovered_by", "")),
        discovered_at=str(payload.get("discovered_at", "")),
        location=_event_input_mapping(payload, "location"),
        tags=payload.get("tags") if isinstance(payload.get("tags"), list) else [item.strip() for item in str(payload.get("tags", "")).split(",") if item.strip()],
        dimensions=_event_input_mapping(payload, "dimensions"),
        source_refs=source_refs,
    )
    for section in ("baseline_impact", "production_track", "technical_track", "commercial_track", "decision", "evidence", "settlement", "audit_cash"):
        value = payload.get(section)
        if isinstance(value, Mapping):
            event[section].update(copy.deepcopy(dict(value)))
    governance = payload.get("governance")
    if isinstance(governance, Mapping):
        for key in ("responsibility", "formal_basis", "emergency_override", "external_approval"):
            if key in governance:
                event["governance"][key] = copy.deepcopy(governance[key])
    validate_event(event)
    state = PROJECT_WORKSPACE.save_event(project_id, event)
    PROJECT_WORKSPACE.append_audit(project_id, "event.created", actor, event["event_id"], {"event_type": event["classification"]["event_type"], "source_refs": event["origin"]["source_refs"]})
    return {"event": _event_public(event, actor), "workspace": state}


def _distill_event_kernel(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("蒸馏请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    if not project_id:
        raise ValueError("蒸馏请求缺少项目标识")
    state = _workspace(project_id)
    local = distill_local_data(state)
    text_value = str(payload.get("text", ""))
    text_source_ref = str(payload.get("text_source_ref", "文本输入")).strip() or "文本输入"
    text = distill_text(text_value, text_source_ref, project_id)
    fused = fuse_distillations(local, text, project_id)
    result = {
        "project_id": project_id,
        "local": local,
        "text": text,
        "fused": fused,
        "summary": {
            "local_fact_count": len(local.get("facts") or []),
            "text_fact_count": len(text.get("facts") or []),
            "fused_fact_count": len(fused.get("fused_facts") or []),
            "conflict_count": len(fused.get("conflicts") or []),
            "claim_count": len(fused.get("claims") or []),
        },
        "local_only": True,
        "external_sent": False,
    }
    state = PROJECT_WORKSPACE.set_event_distillation(project_id, result)
    PROJECT_WORKSPACE.append_audit(project_id, "event.distilled", actor, project_id, {"local_fact_count": result["summary"]["local_fact_count"], "text_fact_count": result["summary"]["text_fact_count"], "conflict_count": result["summary"]["conflict_count"]})
    return {"distillation": _redact_sensitive(result, actor), "events": [_event_public(event, actor) for event in state.get("events") or []]}


def _transition_engineering_event(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("状态推进请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    event_id = str(payload.get("event_id", "")).strip()
    target_status = str(payload.get("target_status", "")).strip()
    state = _workspace(project_id)
    event = next((item for item in state.get("events") or [] if str(item.get("event_id")) == event_id), None)
    if event is None:
        raise FileNotFoundError("工程事件不存在")
    updated = transition_event(event, target_status, actor=actor)
    state = PROJECT_WORKSPACE.save_event(project_id, updated)
    PROJECT_WORKSPACE.append_audit(project_id, "event.transitioned", actor, event_id, {"from": build_state_vector(event)["event"], "to": target_status})
    return {"event": _event_public(updated, actor), "workspace": state}


def _update_engineering_outcome(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Record an Outcome snapshot or move its independent state machine."""
    if not isinstance(payload, dict):
        raise ValueError("Outcome 请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    event_id = str(payload.get("event_id", "")).strip()
    if not project_id or not event_id:
        raise ValueError("Outcome 请求缺少项目或事件标识")
    state = _workspace(project_id)
    event = next((item for item in state.get("events") or [] if str(item.get("event_id")) == event_id), None)
    if event is None:
        raise FileNotFoundError("工程事件不存在")
    operation = str(payload.get("operation", "snapshot")).strip().lower()
    if operation == "transition":
        target_status = str(payload.get("target_status", "")).strip().upper()
        if target_status in {"CONFIRMED", "REVENUE_RECOGNIZED", "SETTLED", "CASH_REALIZED"} and not _can(actor, "view_cost_detail"):
            raise PermissionError("Outcome 的价值确认、结算和回款状态需要造价经理权限")
        updated = transition_outcome(event, target_status, actor=actor, reason=str(payload.get("reason", "")))
        action = "outcome.transitioned"
        details = {"from": build_outcome_vector(event)["status"], "to": target_status}
    else:
        changes = payload.get("changes") if isinstance(payload.get("changes"), Mapping) else {}
        if "values" in changes and not _can(actor, "view_cost_detail"):
            raise PermissionError("Outcome 金额快照仅造价经理可写入")
        updated = record_outcome_snapshot(event, changes, actor=actor, reason=str(payload.get("reason", "")))
        action = "outcome.snapshot_recorded"
        details = {"revision": len(_mapping(updated.get("outcome_track")).get("revisions") or [])}
    validate_event(updated)
    state = PROJECT_WORKSPACE.save_event(project_id, updated)
    PROJECT_WORKSPACE.append_audit(project_id, action, actor, event_id, details)
    return {"event": _event_public(updated, actor), "outcome": build_outcome_vector(updated), "value_leaks": compute_value_leaks(updated), "workspace": state}


def _cross_check_engineering_event(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("互证请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    event_id = str(payload.get("event_id", "")).strip()
    state = _workspace(project_id)
    event = next((item for item in state.get("events") or [] if str(item.get("event_id")) == event_id), None)
    if event is None:
        raise FileNotFoundError("工程事件不存在")
    result = run_cross_check(event)
    PROJECT_WORKSPACE.append_audit(project_id, "event.cross_checked", actor, event_id, {"status": result.get("status"), "conflict_count": result.get("conflict_count", 0)})
    return {"event_id": event_id, "cross_check": result}


def _local_search(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("检索请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    query = str(payload.get("query", "")).strip()
    mode = str(payload.get("mode", "search")).strip().lower() or "search"
    scope = str(payload.get("scope", "all")).strip().lower() or "all"
    stage = str(payload.get("stage", "")).strip()
    category = str(payload.get("category", "")).strip()
    if not project_id or not query:
        raise ValueError("请填写项目和检索内容")
    if mode not in {"search", "ask"}:
        raise ValueError("检索模式不受支持")
    if scope not in {"all", "project", "basis"}:
        raise ValueError("检索范围不受支持")
    if scope == "basis" and not _can(actor, "view_basis"):
        raise PermissionError("当前角色不能检索外部依据库")
    state = _workspace(project_id)
    visible_state = _redact_sensitive(state, actor)
    packet = search_local_evidence(
        visible_state,
        BASIS_WORKSPACE.list(),
        query,
        scope=scope,
        stage=stage,
        category=category,
        source_reader=lambda content_hash: SOURCE_STORE.read(
            SourceDocument(name="local-search.bin", content_hash=content_hash, media_type="application/octet-stream")
        ),
        can_view_source=_can(actor, "view_source"),
        can_view_basis=_can(actor, "view_basis"),
    )
    if mode == "ask":
        packet.update(build_evidence_answer(packet))
    PROJECT_WORKSPACE.append_audit(
        project_id,
        "question.asked" if mode == "ask" else "search.performed",
        actor,
        project_id,
        {
            "query": query[:300],
            "mode": mode,
            "scope": scope,
            "result_count": packet.get("total", 0),
            "answer_mode": packet.get("answer_mode", "local_index") if mode == "ask" else "local_index",
        },
    )
    return packet


def _dashboard_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _dashboard_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _dashboard_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _dashboard_period(snapshots: list[dict[str, Any]], days: int, now: datetime) -> dict[str, Any]:
    cutoff = now - timedelta(days=days)
    recent = [
        snapshot
        for snapshot in snapshots
        if (_dashboard_datetime(snapshot.get("captured_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    rule_counts: Counter[str] = Counter()
    issue_count = 0
    block = warn = info = 0
    for snapshot in recent:
        summary = snapshot.get("summary") or {}
        issue_count += int(summary.get("finding_count", 0) or 0)
        block += int(summary.get("block", 0) or 0)
        warn += int(summary.get("warn", 0) or 0)
        info += int(summary.get("info", 0) or 0)
        for finding in snapshot.get("findings") or []:
            rule_id = str(finding.get("rule_id", "")).strip()
            if rule_id:
                rule_counts[rule_id] += 1
    return {
        "label": f"近{days}天",
        "days": days,
        "review_count": len(recent),
        "issue_count": issue_count,
        "block": block,
        "warn": warn,
        "info": info,
        "recurring_rules": [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in rule_counts.most_common(5)
        ],
    }


def _dashboard_event_status(event: Mapping[str, Any]) -> str:
    return str(event.get("status") or _mapping(event.get("governance")).get("status") or "DISCOVERED")


def _p09_result(state: Mapping[str, Any]) -> dict[str, Any]:
    """Execute P09 from the current workspace without creating a new store."""
    facts = {
        capability_id: (state.get(stage) or {}).get("result")
        for capability_id, stage in (
            ("P01", "contract"),
            ("P02", "boq"),
            ("P03", "drawings"),
            ("P04", "baseline"),
            ("P05", "cost_plan"),
            ("P06", "changes"),
            ("P07", "evidence"),
            ("P08", "review"),
        )
    }
    project = state.get("project") if isinstance(state.get("project"), Mapping) else {}
    project_id = str(project.get("id") or "").strip()
    return dict(RUNTIME.gateway.execute("P09", {
        "project_id": project_id,
        "events": [event for event in state.get("events") or [] if isinstance(event, Mapping)],
        "facts": facts,
    }))


def _line_contracts() -> dict[str, Any]:
    """Publish line and role handoff contracts without exposing runtime paths."""
    return {
        "version": CONTRACT_VERSION,
        "lines": [
            {**dict(LINE_CONTRACTS[line]), "responsibility": line_responsibility(line)}
            for line in LINE_IDS
        ],
        "role_flows": role_flow_contracts(),
        "rules": {
            "preview_is_read_only": True,
            "confirmation_required": True,
            "decision_is_human": True,
            "targets_existing_model": True,
            "new_amount_ledger": False,
        },
    }


def _coordination_response(state: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any]:
    packet = coordination_snapshot(state)
    packet["project"] = dict(state.get("project") or {})
    packet["event_index"] = [
        {
            "event_id": event.get("event_id", ""),
            "title": _mapping(event.get("identity")).get("title", ""),
            "status": event.get("status", "DISCOVERED"),
            "outcome": build_outcome_vector(event),
        }
        for event in state.get("events") or []
        if isinstance(event, Mapping)
    ]
    return _redact_sensitive(packet, actor)


def _append_collaboration(project_id: str, key: str, value: Mapping[str, Any], actor: Mapping[str, Any], action: str) -> dict[str, Any]:
    state = _workspace(project_id)
    bucket = state.setdefault("collaboration", {}).setdefault(key, [])
    bucket.append(dict(value))
    state = PROJECT_WORKSPACE.save(state)
    PROJECT_WORKSPACE.append_audit(project_id, action, actor, str(value.get("task_id") or value.get("decision_id") or project_id), {"status": value.get("status"), "event_id": value.get("event_id", "")})
    return state


def _create_coordination_task(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("协同任务请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    state = _workspace(project_id)
    task = new_task(project_id, payload, actor)
    state = _append_collaboration(project_id, "tasks", task, actor, "coordination.task_created")
    return {"task": task, "collaboration": _coordination_response(state, actor)}


def _update_coordination_task(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("协同任务更新请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    task_id = str(payload.get("task_id", "")).strip()
    state = _workspace(project_id)
    tasks = state.get("collaboration", {}).get("tasks", [])
    task = next((item for item in tasks if str(item.get("task_id")) == task_id), None)
    if task is None:
        raise FileNotFoundError("协同任务不存在")
    updated = update_task(task, str(payload.get("status", "")), actor, str(payload.get("note", "")))
    state["collaboration"]["tasks"] = [updated if str(item.get("task_id")) == task_id else item for item in tasks]
    state = PROJECT_WORKSPACE.save(state)
    PROJECT_WORKSPACE.append_audit(project_id, "coordination.task_updated", actor, task_id, {"status": updated.get("status")})
    return {"task": updated, "collaboration": _coordination_response(state, actor)}


def _create_coordination_decision(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("协同决策请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    state = _workspace(project_id)
    decision = new_decision(project_id, payload, actor, confirm=payload.get("confirm") is True)
    state = _append_collaboration(project_id, "decisions", decision, actor, "coordination.decision_created")
    return {"decision": decision, "collaboration": _coordination_response(state, actor)}


def _confirm_coordination_decision(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("决策确认请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    decision_id = str(payload.get("decision_id", "")).strip()
    state = _workspace(project_id)
    decisions = state.get("collaboration", {}).get("decisions", [])
    decision = next((item for item in decisions if str(item.get("decision_id")) == decision_id), None)
    if decision is None:
        raise FileNotFoundError("协同决策不存在")
    confirmed = confirm_decision(decision, actor)
    state["collaboration"]["decisions"] = [confirmed if str(item.get("decision_id")) == decision_id else item for item in decisions]
    state = PROJECT_WORKSPACE.save(state)
    PROJECT_WORKSPACE.append_audit(project_id, "coordination.decision_confirmed", actor, decision_id, {"decision_type": confirmed.get("decision_type"), "event_id": confirmed.get("event_id")})
    return {"decision": confirmed, "collaboration": _coordination_response(state, actor)}


def _create_relationship(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("关系请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    state = _workspace(project_id)
    relation = new_relation(project_id, payload, actor)
    state.setdefault("relationships", []).append(relation)
    state = PROJECT_WORKSPACE.save(state)
    PROJECT_WORKSPACE.append_audit(project_id, "coordination.relationship_created", actor, relation["relation_id"], {"relation_type": relation.get("relation_type"), "from_id": relation.get("from_id"), "to_id": relation.get("to_id")})
    return {"relationship": relation, "collaboration": _coordination_response(state, actor)}


def _apply_line_mapping_to_event(event: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Merge only confirmed adapter output into the existing Core event."""
    updated = copy.deepcopy(dict(event))
    targets = _mapping(mapping.get("targets"))
    for section, patch in targets.items():
        if not isinstance(patch, Mapping):
            continue
        current = updated.setdefault(section, {})
        if section == "production_track":
            current.update({key: value for key, value in patch.items() if key != "records"})
            current["records"] = [*(current.get("records") or []), *(patch.get("records") or [])]
        elif section == "technical_track":
            for key, value in patch.items():
                if key == "options":
                    current["options"] = [*(current.get("options") or []), *(value or [])]
                elif key in {"drawing_refs", "spec_refs"}:
                    current[key] = list(dict.fromkeys([*(current.get(key) or []), *(value or [])]))
                else:
                    current[key] = value
        elif section == "commercial_track":
            current.update({key: value for key, value in patch.items() if key != "evaluations"})
            current["evaluations"] = [*(current.get("evaluations") or []), *(patch.get("evaluations") or [])]
        else:
            current.update(copy.deepcopy(dict(patch)))
    origin = updated.setdefault("origin", {})
    origin["source_refs"] = list(dict.fromkeys([*(origin.get("source_refs") or []), *(mapping.get("source_refs") or [])]))
    updated.setdefault("governance", {})["updated_at"] = datetime.now(timezone.utc).isoformat()
    validate_event(updated)
    return updated


def _preview_line_adapter(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("业务线预览请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    return {"preview": preview_line_records(str(payload.get("line", "")), project_id, payload.get("records") or [])}


def _confirm_line_adapter(payload: object, actor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("业务线确认请求必须是 JSON 对象")
    project_id = str(payload.get("project_id", "")).strip()
    preview = payload.get("preview")
    confirmed = confirm_line_records(preview, actor)
    state = _workspace(project_id)
    mappings = []
    events = {str(item.get("event_id")): item for item in state.get("events") or [] if isinstance(item, Mapping)}
    for record in confirmed.get("records") or []:
        event_id = str(record.get("event_id", ""))
        event = events.get(event_id)
        if event is None:
            raise FileNotFoundError(f"Core Event 不存在：{event_id}")
        mapping = mapping_for_confirmed_record(str(confirmed.get("line", "")), record, actor)
        updated = _apply_line_mapping_to_event(event, mapping)
        events[event_id] = updated
        mappings.append(mapping)
    state["events"] = list(events.values())
    adaptation = {
        "adaptation_id": f"ADAPT-{uuid4().hex[:10].upper()}",
        "line": confirmed.get("line"),
        "label": confirmed.get("label"),
        "contract_version": confirmed.get("contract_version"),
        "status": "CONFIRMED",
        "record_count": len(confirmed.get("records") or []),
        "confirmed_by": confirmed.get("confirmed_by"),
        "confirmed_at": confirmed.get("confirmed_at"),
        "mapping_targets": confirmed.get("mapping_targets") or [],
        "records": [dict(item) for item in confirmed.get("records") or []],
        "mappings": mappings,
        "human_confirmed": True,
    }
    state.setdefault("line_adaptations", []).append(adaptation)
    state = PROJECT_WORKSPACE.save(state)
    PROJECT_WORKSPACE.append_audit(project_id, "line_adapter.confirmed", actor, adaptation["adaptation_id"], {"line": adaptation["line"], "record_count": adaptation["record_count"], "targets": adaptation["mapping_targets"]})
    return {"adaptation": adaptation, "collaboration": _coordination_response(state, actor), "workspace": state}


def _build_dashboard(state: dict[str, Any], actor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    contract = (state.get("contract") or {}).get("result") or {}
    boq = (state.get("boq") or {}).get("result") or {}
    drawings = (state.get("drawings") or {}).get("result") or {}
    ledger = (state.get("baseline") or {}).get("result") or {}
    plan = (state.get("cost_plan") or {}).get("result") or {}
    changes = (state.get("changes") or {}).get("result") or {}
    evidence = (state.get("evidence") or {}).get("result") or {}
    review = (state.get("review") or {}).get("result") or {}
    summary = plan.get("summary") or {}
    cost_control = plan.get("cost_control")
    plan_baseline_total = _dashboard_decimal(summary.get("contract_subtotal"))
    ledger_baseline_total = _dashboard_decimal((ledger.get("summary") or {}).get("baseline_total"))
    baseline_total = plan_baseline_total if plan_baseline_total is not None else ledger_baseline_total
    pending_count = int(summary.get("pending_item_count", 0) or 0)

    comparison_rows: list[dict[str, Any]] = []
    plan_names = {str(item.get("code", "")): item.get("name", "") for item in plan.get("items") or []}
    total_variance = _dashboard_decimal((cost_control or {}).get("total_variance"))
    over_limit_amount = max(Decimal("0"), -total_variance) if total_variance is not None else None
    comparable_count = 0
    if isinstance(cost_control, dict):
        for item in cost_control.get("items") or []:
            contract_unit = _dashboard_decimal(item.get("contract_unit_price"))
            market_unit = _dashboard_decimal(item.get("market_unit_price"))
            quantity = _dashboard_decimal(item.get("quantity")) or Decimal("0")
            variance = _dashboard_decimal(item.get("variance_amount"))
            contract_amount = contract_unit * quantity if contract_unit is not None else None
            item_over_limit = max(Decimal("0"), -variance) if variance is not None else None
            rate = item_over_limit / contract_amount if item_over_limit and contract_amount else Decimal("0")
            comparable_count += 1
            comparison_rows.append(
                {
                    "code": item.get("code", ""),
                    "name": plan_names.get(str(item.get("code", "")), ""),
                    "quantity": _dashboard_number(quantity),
                    "contract_amount": _dashboard_number(contract_amount),
                    "market_amount": _dashboard_number(market_unit * quantity if market_unit is not None else None),
                    "variance_amount": _dashboard_number(variance),
                    "over_limit_amount": _dashboard_number(item_over_limit),
                    "over_limit_rate": _dashboard_number(rate * 100),
                }
            )
    comparison_rows.sort(key=lambda row: row.get("over_limit_amount") or 0, reverse=True)
    baseline_rate = over_limit_amount / baseline_total if over_limit_amount and baseline_total else Decimal("0")
    comparison = {
        "status": (cost_control or {}).get("comparability") if isinstance(cost_control, dict) else "missing",
        "reason": (cost_control or {}).get("reason", "") if isinstance(cost_control, dict) else "尚未生成可比成本控制结果",
        "baseline_total": _dashboard_number(baseline_total),
        "market_total": _dashboard_number(baseline_total - total_variance if baseline_total is not None and total_variance is not None else None),
        "total_variance": _dashboard_number(total_variance),
        "over_limit_amount": _dashboard_number(over_limit_amount),
        "over_limit_rate": _dashboard_number(baseline_rate * 100),
        "comparable_item_count": comparable_count,
        "rows": comparison_rows[:12],
        "limits": {key: float(value * 100) for key, value in DASHBOARD_LIMITS.items()},
    }

    snapshots = [item for item in state.get("alert_snapshots") or [] if isinstance(item, dict)]
    if not snapshots and review:
        snapshots = [{
            "captured_at": (state.get("review") or {}).get("updated_at"),
            "summary": review.get("summary") or {},
            "findings": review.get("findings") or [],
        }]
    week = _dashboard_period(snapshots, 7, now)
    month = _dashboard_period(snapshots, 30, now)
    last_review_at = (state.get("review") or {}).get("updated_at")
    last_review_dt = _dashboard_datetime(last_review_at)
    alerts: list[dict[str, Any]] = []

    def add_alert(severity: str, rule_id: str, title: str, message: str, view: str) -> None:
        alerts.append({
            "id": rule_id,
            "rule_id": rule_id,
            "severity": severity,
            "risk": _risk_for(severity),
            "title": title,
            "message": message,
            "view": view,
        })

    if not plan and not ledger:
        add_alert("warn", "DASH-BASELINE-01", "成本基线尚未建立", "请先生成成本计划，项目经理暂时无法看到可靠的成本边界。", "plan")
    elif pending_count:
        add_alert("warn", "DASH-BASELINE-02", "仍有待组价清单", f"还有 {pending_count} 个清单项目没有合同单价，成本基线尚未完整。", "plan")

    if cost_control is None:
        if plan:
            add_alert("warn", "DASH-COMPARE-01", "尚未形成成本比对", "请录入市场参考价并声明价格口径，系统才能判断成本是否超出基线。", "plan")
    elif comparison["status"] == "conflicted":
        add_alert("block", "DASH-COMPARE-02", "价格口径冲突", str(comparison["reason"] or "合同基线与参考价不能直接比较。"), "plan")
    elif comparison["status"] != "comparable":
        add_alert("warn", "DASH-COMPARE-03", "成本比对仅供参考", str(comparison["reason"] or "价格口径声明不完整，偏差数不能作为结论。"), "plan")
    elif over_limit_amount and baseline_rate >= DASHBOARD_LIMITS["critical_rate"]:
        add_alert("block", "DASH-LIMIT-02", "成本超限需立即处理", f"参考成本高于合同基线 {float(over_limit_amount):,.2f}，偏差约 {float(baseline_rate * 100):.2f}%。", "plan")
    elif over_limit_amount and baseline_rate >= DASHBOARD_LIMITS["warn_rate"]:
        add_alert("warn", "DASH-LIMIT-01", "成本接近或超过预警线", f"参考成本高于合同基线 {float(over_limit_amount):,.2f}，偏差约 {float(baseline_rate * 100):.2f}%。", "plan")

    if not review:
        add_alert("warn", "DASH-REVIEW-01", "尚未完成结算初审", "问题清单、口径冲突和发布门禁还没有形成，请运行结算初审。", "review")
    else:
        for finding in (review.get("findings") or [])[:5]:
            severity = str(finding.get("severity", "info"))
            add_alert(
                severity,
                f"REVIEW-{finding.get('rule_id', 'ITEM')}-{finding.get('row', 'ALL')}",
                finding.get("risk", {}).get("label", "审查事项"),
                str(finding.get("message", "请查看结算初审结果。")),
                "review",
            )
    if plan and week["review_count"] == 0:
        add_alert("warn", "DASH-CADENCE-01", "近7天没有审查记录", "建议每周至少运行一次初审，及时发现清单、价格和资料变化。", "review")
    elif last_review_dt and now - last_review_dt > timedelta(days=7):
        add_alert("warn", "DASH-CADENCE-02", "初审记录已超过7天", "请重新接入最新资料并运行初审，避免沿用过期判断。", "review")
    if month["issue_count"] and month["issue_count"] > week["issue_count"]:
        add_alert("info", "DASH-TREND-01", "月度问题多于本周", f"近30天累计 {month['issue_count']} 个问题，本周为 {week['issue_count']} 个；请关注重复问题。", "dashboard")

    contract_summary = contract.get("summary") or {}
    if not contract or contract_summary.get("missing_field_count", 0) > 0:
        missing = int(contract_summary.get("missing_field_count", 0) or 0)
        add_alert("warn", "DASH-P01-01", "合同主数据尚未完整", f"合同资料仍有 {missing or '若干'} 项关键字段待确认。", "contract")
    drawing_summary = drawings.get("summary") or {}
    if not drawings:
        add_alert("info", "DASH-P03-01", "尚未建立图纸登记册", "请登记施工图、版本和审阅状态，避免变更和计量缺少图纸依据。", "drawings")
    elif drawing_summary.get("unreviewed_count", 0):
        add_alert("warn", "DASH-P03-02", "存在待审图纸", f"还有 {drawing_summary.get('unreviewed_count')} 张图纸未完成审阅。", "drawings")
    if not plan and ledger:
        add_alert("info", "DASH-P04-01", "已建立零号台账，尚未生成成本计划", "零号台账已形成开局基线；补充合同单价后继续生成 P05 成本计划。", "plan")
    change_summary = changes.get("summary") or {}
    if change_summary.get("pending_count", 0):
        add_alert("warn", "DASH-P06-01", "存在待审批变更", f"有 {change_summary.get('pending_count')} 项变更等待决策，净影响 {change_summary.get('net_amount', 0):,.2f}。", "changes")
    evidence_summary = evidence.get("summary") or {}
    if evidence_summary.get("unverified_count", 0):
        add_alert("info", "DASH-P07-01", "存在待核验证据关联", f"有 {evidence_summary.get('unverified_count')} 条证据关联尚未核验。", "evidence")

    events = [item for item in state.get("events") or [] if isinstance(item, Mapping)]
    event_alerts = []
    event_statuses: Counter[str] = Counter()
    for event in events:
        event_statuses[_dashboard_event_status(event)] += 1
        for event_alert in evaluate_event_rules(event):
            event_alerts.append({"event_id": event.get("event_id", ""), **event_alert})
            add_alert(
                str(event_alert.get("severity", "info")),
                f"{event_alert.get('rule_id', 'EVENT')}-{event.get('event_id', '')}",
                str(event_alert.get("title", "工程事件提醒")),
                f"{event.get('event_id', '')}：{event_alert.get('message', '')}",
                "events",
            )

    # Negative-entropy management view: one derived funnel and one queue.
    # Amounts are read from the existing P01-P08 records as snapshots; no new
    # value ledger is created here.
    outcome_stage_labels = {
        "physical": "实体完成",
        "evidence_ready": "证据完整",
        "submitted": "已申报",
        "confirmed": "已确认",
        "revenue": "收入成立",
        "settled": "已结算",
        "paid": "已回款",
    }
    funnel_totals: dict[str, Decimal] = {key: Decimal("0") for key in outcome_stage_labels}
    funnel_counts: Counter[str] = Counter()
    outcome_statuses: Counter[str] = Counter()
    outcome_types: Counter[str] = Counter()
    leak_items: list[dict[str, Any]] = []
    daily_queue: list[dict[str, Any]] = []
    for event in events:
        outcome = _mapping(event.get("outcome_track"))
        outcome_status = str(outcome.get("status") or "NOT_FORMED")
        outcome_statuses[outcome_status] += 1
        for outcome_type in outcome.get("types") or []:
            outcome_types[str(outcome_type)] += 1
        values = _mapping(outcome.get("values"))
        event_title = str(_mapping(event.get("identity")).get("title") or "").strip() or str(event.get("event_id", ""))
        for stage in outcome_stage_labels:
            amount = _dashboard_decimal(values.get(stage))
            if amount is not None:
                funnel_totals[stage] += amount
                funnel_counts[stage] += 1
        leaks = compute_value_leaks(event)
        for leak in leaks.get("items") or []:
            leak_items.append({**leak, "title": event_title, "severity": str(_mapping(event.get("classification")).get("severity") or "")})
        event_alerts_for_queue = evaluate_event_rules(event)
        discovered_at = _dashboard_datetime(_mapping(event.get("origin")).get("discovered_at"))
        days_open = max(0, (now - discovered_at).days) if discovered_at else None
        if event_alerts_for_queue or outcome_status not in {"CASH_REALIZED", "REJECTED", "ABANDONED"}:
            daily_queue.append({
                "event_id": event.get("event_id", ""),
                "title": event_title,
                "event_status": _dashboard_event_status(event),
                "outcome_status": outcome_status,
                "value_leak_count": int(leaks.get("count", 0) or 0),
                "alert_count": len(event_alerts_for_queue),
                "days_open": days_open,
                "time_stage": outcome_status if outcome_status != "NOT_FORMED" else _dashboard_event_status(event),
                "priority": len(event_alerts_for_queue) * 10 + int(leaks.get("total", 0) or 0),
            })
    funnel: list[dict[str, Any]] = []
    previous_amount: Decimal | None = None
    for stage, label in outcome_stage_labels.items():
        amount = funnel_totals[stage]
        conversion = None if previous_amount in (None, Decimal("0")) else float((amount / previous_amount) * 100)
        funnel.append({"stage": stage, "label": label, "amount": _dashboard_number(amount), "event_count": funnel_counts[stage], "conversion_rate": conversion})
        previous_amount = amount if amount > 0 else previous_amount
    leak_items.sort(key=lambda item: item.get("amount", 0), reverse=True)
    daily_queue.sort(key=lambda item: item.get("priority", 0), reverse=True)
    outcome_management = {
        "funnel": funnel,
        "status_counts": dict(outcome_statuses),
        "type_counts": dict(outcome_types),
        "value_leak_total": round(sum(float(item.get("amount", 0) or 0) for item in leak_items), 2),
        "value_leak_count": len(leak_items),
        "value_leaks": leak_items[:12],
        "daily_queue": daily_queue[:12],
        "forecast": {
            "status": "insufficient_data",
            "reason": "当前项目尚未提供实际成本、剩余工程成本和风险权重；系统不猜测 EAC 利润。",
            "available": ["confirmed", "submitted", "settled", "paid"],
            "missing": ["actual_cost", "remaining_cost", "risk_weight"],
        },
        "rules": {
            "single_fact_source": True,
            "event_closed_not_outcome_closed": True,
            "derived_values_only": True,
        },
    }

    # The dashboard is a presentation of the registered P09 capability.  The
    # legacy inline calculation above is kept as a migration-safe fallback,
    # while the gateway projection is now the authoritative result.
    p09 = _p09_result(state)
    # P09 is a management projection, not a general-purpose operational
    # panel.  Keep it visible only to the project manager and cost manager;
    # other roles still receive their dashboard metrics without a second,
    # unscoped outcome view.
    if not _actor_roles(actor).intersection(_CAPABILITY_ROLE_ACCESS["p09"]):
        p09 = {
            "capability_id": "P09",
            "status": "restricted",
            "summary": {"status": "restricted", "message": "P09 全过程成果经营仅对项目经理和造价经理开放"},
            "funnel": [],
            "value_leaks": [],
            "daily_queue": [],
            "rules": {"single_fact_source": True, "derived_values_only": True},
        }
    outcome_management = p09

    alerts.sort(key=lambda item: item["risk"]["priority"], reverse=True)
    dashboard = {
        "project": state.get("project") or {},
        "audience": (actor or {}).get("role", "cost_manager"),
        "generated_at": now.isoformat(),
        "baseline": {
            "status": "ready" if plan or ledger else "missing",
            "source": "P05 cost plan" if plan else "P04 zero ledger",
            "boq_item_count": int(boq.get("item_count", len(boq.get("items") or [])) or 0),
            "contract_item_count": int(summary.get("contract_item_count", 0) or 0),
            "contract_subtotal": _dashboard_number(baseline_total),
            "zero_ledger_total": _dashboard_number(ledger_baseline_total),
            "pending_item_count": pending_count,
        },
        "capabilities": {
            "P01": contract.get("summary") or {},
            "P02": boq.get("summary") or {"item_count": boq.get("item_count", 0)},
            "P03": drawings.get("summary") or {},
            "P04": ledger.get("summary") or {},
            "P05": plan.get("summary") or {},
            "P06": changes.get("summary") or {},
            "P07": evidence.get("summary") or {},
            "P08": review.get("summary") or {},
            "P09": p09.get("summary") or {},
        },
        "comparison": comparison,
        "review": {
            "status": "completed" if review else "missing",
            "last_review_at": last_review_at,
            "publishable": review.get("publishable") if review else None,
            "current_summary": review.get("summary") or {},
        },
        "periods": {"week": week, "month": month},
        "events": {
            "count": len(events),
            "status_counts": dict(event_statuses),
            "alert_count": len(event_alerts),
            "state_vectors": [
                {"event_id": event.get("event_id", ""), "title": _mapping(event.get("identity")).get("title", ""), "state_vector": build_state_vector(event)}
                for event in events[:12]
            ],
        },
        "outcome_management": outcome_management,
        "alerts": alerts[:12],
        "recent_issues": (review.get("findings") or [])[:12],
    }
    if (actor or {}).get("role") == ROLE_PROJECT_MANAGER:
        dashboard["access"] = "kpi_only"
        dashboard["capabilities"] = {
            capability_id: {"status": "已建立" if details else "待建立"}
            for capability_id, details in dashboard["capabilities"].items()
        }
        dashboard["comparison"]["rows"] = []
        dashboard["recent_issues"] = []
        dashboard["outcome_management"] = _redact_sensitive(dashboard.get("outcome_management") or {}, actor)
    elif not _can(actor, "view_cost_detail"):
        dashboard = _redact_sensitive(dashboard, actor)
        dashboard["access"] = "operational_redacted"
        dashboard["comparison"]["rows"] = []
        dashboard["recent_issues"] = []
        for alert in dashboard.get("alerts", []):
            if alert.get("rule_id") == "DASH-P06-01":
                alert["message"] = "存在待审批变更，金额影响已按角色权限隐藏。"
    else:
        dashboard["access"] = "full"
    return dashboard


def _report_html(state: dict[str, Any]) -> bytes:
    project = state["project"]
    contract = (state.get("contract") or {}).get("result") or {}
    boq = (state.get("boq") or {}).get("result") or {}
    drawings = (state.get("drawings") or {}).get("result") or {}
    ledger = (state.get("baseline") or {}).get("result") or {}
    plan = (state.get("cost_plan") or {}).get("result") or {}
    changes = (state.get("changes") or {}).get("result") or {}
    evidence = (state.get("evidence") or {}).get("result") or {}
    review = (state.get("review") or {}).get("result") or {}
    items = plan.get("items") or boq.get("items") or []
    rows = "".join(
        "<tr>" + "".join(
            f"<td>{html.escape(str(item.get(key, '')))}</td>"
            for key in ("code", "name", "unit", "quantity", "unit_price", "amount", "status")
        ) + "</tr>"
        for item in items
    )
    gate = "允许发布" if review.get("publishable") else "需要处理"
    gate_color = "#16734a" if review.get("publishable") else "#a12b24"
    capability_rows = [
        ("P01 合同与招采依据", "已建立" if contract else "未建立", (contract.get("summary") or {}).get("missing_field_count", "—")),
        ("P02 清单资料", "已建立" if boq else "未建立", boq.get("item_count", "—")),
        ("P03 图纸登记", "已建立" if drawings else "未建立", (drawings.get("summary") or {}).get("drawing_count", "—")),
        ("P04 零号台账", "已建立" if ledger else "未建立", (ledger.get("summary") or {}).get("baseline_total", "—")),
        ("P05 成本计划", "已建立" if plan else "未建立", (plan.get("summary") or {}).get("contract_subtotal", "—")),
        ("P06 变更管理", "已建立" if changes else "未建立", (changes.get("summary") or {}).get("pending_count", "—")),
        ("P07 证据关联", "已建立" if evidence else "未建立", (evidence.get("summary") or {}).get("link_count", "—")),
        ("P08 结算初审", "已建立" if review else "未建立", (review.get("summary") or {}).get("finding_count", "—")),
    ]
    capability_html = "".join(
        f"<tr><td>{html.escape(str(label))}</td><td>{html.escape(str(status))}</td><td>{html.escape(str(value))}</td></tr>"
        for label, status, value in capability_rows
    )
    body = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{html.escape(str(project['name']))} - 造价工作报告</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:36px;color:#222}}h1{{margin-bottom:6px}}.meta{{color:#666;margin-bottom:24px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #bbb;padding:7px;text-align:left;font-size:12px}}th{{background:#eee}}</style>
</head><body><h1>{html.escape(str(project['name']))} · 造价工作报告</h1>
<div class="meta">项目编号：{html.escape(str(project['id']))}　生成时间：{html.escape(str(project.get('updated_at', '')))}</div>
<h2>工作状态</h2><p style="font-size:18px;font-weight:bold;color:{gate_color}">结算初审：{gate}</p>
<h2>P01–P08 能力覆盖</h2><table><thead><tr><th>能力</th><th>状态</th><th>摘要</th></tr></thead><tbody>{capability_html}</tbody></table>
<h2>成本计划</h2><p>合同计划小计：{html.escape(str((plan.get('summary') or {}).get('contract_subtotal', '—')))}　待组价：{html.escape(str((plan.get('summary') or {}).get('pending_item_count', '—')))}</p>
<table><thead><tr><th>编码</th><th>项目</th><th>单位</th><th>工程量</th><th>合同单价</th><th>金额</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table>
<h2>审查事项</h2><ul>{''.join(f'<li>{html.escape(str(f.get("message", "")))}</li>' for f in review.get('findings', [])) or '<li>未发现审查事项</li>'}</ul>
</body></html>"""
    return body.encode("utf-8")


def _cost_plan_csv(state: dict[str, Any]) -> bytes:
    plan = (state.get("cost_plan") or {}).get("result") or {}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["项目编码", "项目名称", "单位", "工程量", "合同单价", "金额", "状态"])
    for item in plan.get("items", []):
        writer.writerow([item.get("code"), item.get("name"), item.get("unit"), item.get("quantity"), item.get("unit_price"), item.get("amount"), item.get("status")])
    return output.getvalue().encode("utf-8-sig")


def _xlsx_bytes(sheet_name: str, headers: list[str], rows: list[list[object]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(max(width, 10), 36)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _boq_csv(state: dict[str, Any]) -> bytes:
    boq = (state.get("boq") or {}).get("result") or {}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["项目编码", "项目名称", "单位", "工程量"])
    for item in boq.get("items", []):
        writer.writerow([item.get("code"), item.get("name"), item.get("unit"), item.get("quantity")])
    return output.getvalue().encode("utf-8-sig")


def _boq_xlsx(state: dict[str, Any]) -> bytes:
    boq = (state.get("boq") or {}).get("result") or {}
    rows = [
        [item.get("code"), item.get("name"), item.get("unit"), item.get("quantity")]
        for item in boq.get("items", [])
    ]
    return _xlsx_bytes("清单", ["项目编码", "项目名称", "单位", "工程量"], rows)


def _cost_plan_xlsx(state: dict[str, Any]) -> bytes:
    plan = (state.get("cost_plan") or {}).get("result") or {}
    rows = [
        [item.get("code"), item.get("name"), item.get("unit"), item.get("quantity"), item.get("unit_price"), item.get("amount"), item.get("status")]
        for item in plan.get("items", [])
    ]
    return _xlsx_bytes(
        "成本计划",
        ["项目编码", "项目名称", "单位", "工程量", "合同单价", "金额", "状态"],
        rows,
    )


def _source_reader(source: dict[str, Any]) -> bytes:
    document = SourceDocument(
        name=str(source.get("name", "source.bin")),
        content_hash=str(source["content_hash"]),
        media_type=str(source.get("media_type", "application/octet-stream")),
    )
    return SOURCE_STORE.read(document)


def _project_bundle(state: dict[str, Any]) -> bytes:
    return build_project_bundle(state, _source_reader)


def _import_project_bundle(content_type: str, body: bytes) -> dict[str, Any]:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("项目交换包导入需要 multipart/form-data")
    fields = _multipart_fields(content_type, body)
    filename, content = fields.get("file", ("", b""))
    if not filename or not content:
        raise ValueError("请选择 BuildCostIQ 项目交换包")
    if Path(filename).suffix.lower() != ".zip":
        raise ValueError("项目交换包必须是 .zip 文件")

    try:
        with ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names or "project.json" not in names:
                raise ValueError("交换包缺少项目清单")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != "buildcostiq-project-bundle" or manifest.get("version") != 1:
                raise ValueError("不支持的 BuildCostIQ 项目交换包版本")
            imported = json.loads(archive.read("project.json").decode("utf-8"))
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("项目交换包无法读取") from exc

    project = imported.get("project")
    if not isinstance(project, dict):
        raise ValueError("交换包缺少项目资料")
    project_id = str(project.get("id", "")).strip()
    project_name = str(project.get("name", "")).strip()
    if not project_id or not project_name:
        raise ValueError("交换包中的项目资料不完整")
    state: dict[str, Any] = {
        "project": project,
        "sources": [],
        "boq": imported.get("boq"),
        "cost_plan": imported.get("cost_plan"),
        "review": imported.get("review"),
    }
    original_sources = imported.get("sources") or []
    if not isinstance(original_sources, list):
        raise ValueError("交换包中的资料清单无效")
    with ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
        for original in original_sources:
            if not isinstance(original, dict):
                continue
            name = PurePosixPath(str(original.get("name", "source.bin"))).name or "source.bin"
            entry = f"sources/{name}"
            if entry not in names:
                continue
            raw = archive.read(entry)
            source = SOURCE_STORE.ingest(
                name,
                raw,
                str(original.get("media_type", mimetypes.guess_type(name)[0] or "application/octet-stream")),
            )
            metadata = {**original}
            recognition = dict(metadata.get("recognition") or {})
            artifact_meta = dict(recognition.get("artifact") or {})
            artifact_name = PurePosixPath(str(artifact_meta.get("name", ""))).name
            artifact_entry = f"derived/{artifact_name}" if artifact_name else ""
            if artifact_entry and artifact_entry in names:
                artifact_raw = archive.read(artifact_entry)
                artifact = SOURCE_STORE.ingest(artifact_name, artifact_raw, "text/markdown")
                artifact_meta.update(
                    {
                        "name": artifact_name,
                        "document_id": artifact.id,
                        "content_hash": artifact.content_hash,
                        "media_type": artifact.media_type,
                        "storage_path": str(SOURCE_STORE.path_for(artifact)),
                        "size": len(artifact_raw),
                    }
                )
                recognition["artifact"] = artifact_meta
                metadata["recognition"] = recognition
            state["sources"].append(
                {
                    **metadata,
                    "name": name,
                    "document_id": source.id,
                    "content_hash": source.content_hash,
                    "media_type": source.media_type,
                    "storage_path": str(SOURCE_STORE.path_for(source)),
                    "size": len(raw),
                }
            )
    return PROJECT_WORKSPACE.save(state)


def _health() -> dict[str, Any]:
    return {
        "service": "BuildCostIQ WebUI",
        "runtime": RUNTIME.health(),
        "deployment": DEPLOYMENT_CONFIG.public(),
        "review_capability": "P08",
        "business_capabilities": [f"P{i:02d}" for i in range(1, 10)],
        "dependencies": {"external_runtime": False, "project_dependency": "openpyxl+pypdf+markitdown"},
        "privacy": {"default_mode": "local_only", "external_send": "explicit_consent_required"},
        "release_highlights": "v0.8.0-rc5：P09 仍只由 P01–P08 事实派生；人员名册按项目独立维护，首页按岗位提供输入→操作→成果→复核手册；项目经理或授权行政人员可在当前项目新增人员",
    }


def _deployment_status() -> dict[str, Any]:
    """Return deployment metadata without exposing absolute storage paths."""

    return {
        "service": "BuildCostIQ WebUI",
        "deployment": DEPLOYMENT_STORAGE.status(),
        "data_authority": "central_service" if DEPLOYMENT_CONFIG.mode == "central" else "this_node",
        "storage_policy": "终端只通过 API 读写；共享文件夹不作为实时数据库。",
    }


def _architecture() -> dict[str, Any]:
    return {
        **ARCHITECTURE,
        "registered": list(RUNTIME.gateway.registered),
        "version": RUNTIME.health()["version"],
    }


class BuildCostWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class BuildCostHandler(BaseHTTPRequestHandler):
    server_version = f"BuildCostIQWebUI/{current_version()}"

    @staticmethod
    def _content_disposition(disposition: str, filename: str) -> str:
        safe_name = Path(filename).name.replace('"', "").replace("\r", "").replace("\n", "") or "source.bin"
        fallback = safe_name.encode("ascii", "ignore").decode("ascii") or "source.bin"
        encoded = quote(safe_name, safe="")
        return f'{disposition}; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'

    def _write_json(self, payload: object, status: int = 200) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _write_text(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _write_download(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", self._content_disposition("attachment", filename))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _write_inline(self, body: bytes, content_type: str, filename: str) -> None:
        safe_name = Path(filename).name.replace('"', "") or "source.bin"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", self._content_disposition("inline", safe_name))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self) -> object:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large")
        return self.rfile.read(length)

    def _serve_static(self, request_path: str) -> None:
        relative = unquote(request_path.lstrip("/")) or "index.html"
        candidate = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT not in candidate.parents or not candidate.is_file():
            self._write_text(b"Not found", "text/plain; charset=utf-8", 404)
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self._write_text(candidate.read_bytes(), f"{content_type}; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/api/auth/me":
            try:
                self._write_json({"user": _require_actor(self.headers)})
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 401)
        elif path == "/api/personnel":
            try:
                _require_actor(self.headers, "manage_personnel")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0].strip() or None
                self._write_json(AUTH_STORE.personnel_snapshot(project_id))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
        elif path == "/api/source/view":
            try:
                actor = _require_actor(self.headers, "view_source")
                query = parse_qs(parsed.query)
                content, content_type, filename = _source_view(
                    query.get("project_id", [""])[0],
                    query.get("source_id", [""])[0],
                    query.get("derived", ["0"])[0] == "1",
                    actor,
                )
                self._write_inline(content, content_type, filename)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 401)
            except (FileNotFoundError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/basis":
            try:
                _require_actor(self.headers, "view_basis")
                self._write_json({"categories": list(BASIS_CATEGORIES), "items": [_basis_public(item) for item in BASIS_WORKSPACE.list()]})
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
        elif path == "/api/basis/view":
            try:
                _require_actor(self.headers, "view_basis")
                query = parse_qs(parsed.query)
                content, content_type, filename = _basis_view(query.get("basis_id", [""])[0], query.get("derived", ["0"])[0] == "1")
                self._write_inline(content, content_type, filename)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/health":
            self._write_json(_health())
        elif path == "/api/deployment":
            self._write_json(_deployment_status())
        elif path == "/api/architecture":
            self._write_json(_architecture())
        elif path == "/api/sample":
            self._write_json(DEMO_REQUEST)
        elif path == "/api/connectors":
            self._write_json({"connectors": connector_catalog()})
        elif path == "/api/line-contracts":
            self._write_json(_line_contracts())
        elif path == "/api/recognition/catalog":
            self._write_json({"recognizers": recognition_catalog()})
        elif path == "/api/audit":
            try:
                actor = _require_actor(self.headers, "view_audit")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                state = _workspace(project_id)
                self._write_json({"audit_log": _redact_sensitive(state.get("audit_log") or [], actor)})
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/dashboard":
            try:
                actor = _require_actor(self.headers, "view_dashboard")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                self._write_json(_build_dashboard(_workspace(project_id), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/p09":
            try:
                actor = _require_actor(self.headers, "view_dashboard")
                _require_capability_role(actor, "p09")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                self._write_json(_redact_sensitive(_p09_result(_workspace(project_id)), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/collaboration":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                self._write_json(_coordination_response(_workspace(project_id), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/event-kernel":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                self._write_json(_event_kernel_response(_workspace(project_id), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/workspace":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                self._write_json(_visible_workspace(_workspace(project_id), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path.startswith("/api/workspace/"):
            project_id = unquote(path.removeprefix("/api/workspace/").split("/", 1)[0])
            try:
                actor = _require_actor(self.headers, "view_workspace")
                state = _workspace(project_id)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
                return
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
                return
            if path.endswith("/report"):
                if not _can(actor, "view_cost_detail"):
                    self._write_json({"error": "当前角色不能导出成本明细报告"}, 403)
                    return
                self._write_download(_report_html(state), "text/html; charset=utf-8", "buildcostiq-report.html")
            elif path.endswith("/boq.csv"):
                self._write_download(_boq_csv(state), "text/csv; charset=utf-8", "boq.csv")
            elif path.endswith("/boq.xlsx"):
                self._write_download(
                    _boq_xlsx(state),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "boq.xlsx",
                )
            elif path.endswith("/cost-plan.csv"):
                if not _can(actor, "view_cost_detail"):
                    self._write_json({"error": "当前角色不能导出成本明细"}, 403)
                    return
                self._write_download(_cost_plan_csv(state), "text/csv; charset=utf-8", "cost-plan.csv")
            elif path.endswith("/cost-plan.xlsx"):
                if not _can(actor, "view_cost_detail"):
                    self._write_json({"error": "当前角色不能导出成本明细"}, 403)
                    return
                self._write_download(
                    _cost_plan_xlsx(state),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "cost-plan.xlsx",
                )
            elif path.endswith("/bundle"):
                if not _can(actor, "view_cost_detail"):
                    self._write_json({"error": "当前角色不能导出包含成本明细的项目交换包"}, 403)
                    return
                self._write_download(
                    _project_bundle(state),
                    "application/zip",
                    f"{state['project']['id']}-buildcostiq.zip",
                )
            else:
                self._write_json(_visible_workspace(state, actor))
        else:
            self._serve_static(path)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler API
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path == "/api/auth/register":
            try:
                self._write_json(_auth_register(self._read_json()))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/auth/login":
            try:
                self._write_json(_auth_login(self._read_json()))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 401)
            return
        if path == "/api/auth/logout":
            token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            SESSIONS.pop(token, None)
            self._write_json({"ok": True})
            return
        if path == "/api/search":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                _require_capability_role(actor, "search")
                self._write_json(_local_search(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/line-adapter/preview":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_preview_line_adapter(self._read_json()), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, LineContractError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/line-adapter/confirm":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_confirm_line_adapter(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, LineContractError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/collaboration/task":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_create_coordination_task(self._read_json(), actor), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, CoordinationError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/collaboration/task/status":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_update_coordination_task(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, CoordinationError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/collaboration/decision":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_create_coordination_decision(self._read_json(), actor), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, CoordinationError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/collaboration/decision/confirm":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_confirm_coordination_decision(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, CoordinationError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/relationships":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_create_relationship(self._read_json(), actor), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, CoordinationError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/event-kernel/distill":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_distill_event_kernel(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/event-kernel/events":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_create_engineering_event(self._read_json(), actor), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/event-kernel/transition":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                payload = self._read_json()
                if isinstance(payload, dict) and str(payload.get("target_status", "")) in {"DECIDED", "APPROVAL", "EXECUTING", "CLOSED"} and not _can(actor, "view_cost_detail"):
                    raise PermissionError("状态决策和关闭需要造价经理权限")
                self._write_json(_redact_sensitive(_transition_engineering_event(payload, actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/event-kernel/outcome":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_update_engineering_outcome(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/event-kernel/check":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                self._write_json(_cross_check_engineering_event(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventKernelError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/personnel":
            try:
                actor = _require_actor(self.headers, "manage_personnel")
                self._write_json(_personnel_create(self._read_json(), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/personnel/authorize":
            try:
                actor = _require_actor(self.headers, "authorize_personnel_admin")
                self._write_json(_personnel_authorize(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/personnel/delete":
            try:
                actor = _require_actor(self.headers, "manage_personnel")
                self._write_json(_personnel_delete(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/personnel/rename":
            try:
                actor = _require_actor(self.headers, "manage_personnel")
                self._write_json(_personnel_rename(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/personnel/roles":
            try:
                actor = _require_actor(self.headers, "manage_personnel")
                self._write_json(_personnel_roles(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/source/modify":
            try:
                actor = _require_actor(self.headers, "modify_source")
                self._write_json(_source_modify(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/source/delete":
            try:
                actor = _require_actor(self.headers, "delete_source")
                self._write_json(_source_delete(self._read_json(), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/project":
            try:
                actor = _require_actor(self.headers, "view_workspace")
                self._write_json(_visible_workspace(_project(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/source/upload":
            try:
                actor = _require_actor(self.headers, "upload_source")
                self._write_json(_redact_sensitive(_source_upload(self.headers.get("Content-Type", ""), self._read_body(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/basis/upload":
            try:
                actor = _require_actor(self.headers, "upload_basis")
                self._write_json(_basis_upload(self.headers.get("Content-Type", ""), self._read_body(), actor), 201)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/basis/reference":
            try:
                actor = _require_actor(self.headers, "reference_basis")
                result = _basis_reference(self._read_json(), actor)
                self._write_json(_redact_sensitive(result, actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            return
        if path == "/api/source/recognize":
            try:
                actor = _require_actor(self.headers, "recognize_source")
                self._write_json(_redact_sensitive(_recognize_source(self._read_json(), actor), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/workspace/import":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                self._write_json(_redact_sensitive(_import_project_bundle(self.headers.get("Content-Type", ""), self._read_body()), actor))
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/boq/upload":
            try:
                actor = _require_actor(self.headers, "edit_business_data")
                result = _boq_upload(self.headers.get("Content-Type", ""), self._read_body(), actor)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
                return
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
                return
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
                return
            self._write_json(_redact_sensitive(result, actor))
            return

        try:
            actor = _require_actor(self.headers, "edit_business_data")
        except PermissionError as exc:
            self._write_json({"error": str(exc)}, 403)
            return
        if path == "/api/review" and not _can(actor, "view_cost_detail"):
            self._write_json({"error": "结算初审包含敏感成本明细，仅造价经理可执行"}, 403)
            return
        capability_by_path = {
            "/api/contract": "contract",
            "/api/boq": "boq",
            "/api/drawings": "drawings",
            "/api/baseline": "baseline",
            "/api/cost-plan": "cost-plan",
            "/api/changes": "changes",
            "/api/evidence": "evidence",
            "/api/review": "review",
        }
        capability = capability_by_path.get(urlsplit(self.path).path)
        if capability:
            try:
                _require_capability_role(actor, capability)
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 403)
                return
        handlers = {
            "/api/contract": lambda payload: _contract(payload, actor),
            "/api/boq": lambda payload: _boq(payload, actor),
            "/api/drawings": lambda payload: _drawings(payload, actor),
            "/api/baseline": lambda payload: _baseline(payload, actor),
            "/api/cost-plan": lambda payload: _cost_plan(payload, actor),
            "/api/changes": lambda payload: _changes(payload, actor),
            "/api/evidence": lambda payload: _evidence(payload, actor),
            "/api/review": lambda payload: _review(payload, actor),
        }
        handler = handlers.get(urlsplit(self.path).path)
        if handler is None:
            self._write_json({"error": "Not found"}, 404)
            return
        try:
            result = handler(self._read_json())
        except PermissionError as exc:
            self._write_json({"error": str(exc)}, 403)
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._write_json({"error": str(exc)}, 422)
            return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._write_json({"error": str(exc)}, 500)
            return
        self._write_json(_redact_sensitive(result, actor))

    def log_message(self, format: str, *args: object) -> None:
        print(f"[webui] {self.address_string()} - {format % args}")


def create_server(host: str = "127.0.0.1", port: int = 8787) -> BuildCostWebServer:
    return BuildCostWebServer((host, port), BuildCostHandler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the local BuildCostIQ WebUI")
    parser.add_argument("--host", default=None, help="监听地址；中央部署通常使用 0.0.0.0 并配合防火墙")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--deployment-mode", choices=("single-node", "central", "edge"), default=None)
    parser.add_argument("--node-id", default=None, help="服务节点标识")
    parser.add_argument("--data-root", default=None, help="中央数据根目录，例如 D:/BuildCostIQData")
    parser.add_argument("--backup-root", default=None, help="备份根目录；不作为实时数据库")
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    overrides = {
        "BUILDCOSTIQ_HOST": args.host,
        "BUILDCOSTIQ_PORT": str(args.port) if args.port is not None else None,
        "BUILDCOSTIQ_DEPLOYMENT_MODE": args.deployment_mode,
        "BUILDCOSTIQ_NODE_ID": args.node_id,
        "BUILDCOSTIQ_DATA_ROOT": args.data_root,
        "BUILDCOSTIQ_BACKUP_ROOT": args.backup_root,
    }
    for key, value in overrides.items():
        if value is not None:
            environment[key] = value
    config = DeploymentConfig.from_environment(environment)
    _configure_deployment(config)
    server = create_server(config.host, config.port)
    print(f"BuildCostIQ WebUI: http://{config.host}:{config.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
