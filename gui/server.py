from __future__ import annotations

import argparse
import csv
import html
import io
import json
import mimetypes
import os
import secrets
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from adapters import (
    ImmutableSourceStore,
    LocalAuthStore,
    LocalProjectWorkspace,
    ROLE_PERMISSIONS,
    ROLE_PROJECT_MANAGER,
)
from adapters.connectors import build_project_bundle, connector_catalog
from adapters.recognition import RecognitionError, recognition_catalog, recognize_source
from core import Runtime
from core.models import SourceDocument
from plugins import build_default_plugins


STATIC_ROOT = Path(__file__).resolve().parent / "static"
RUNTIME = Runtime(build_default_plugins())
MAX_BODY_BYTES = 50_000_000
PROJECT_WORKSPACE = LocalProjectWorkspace(os.environ.get("BUILDCOSTIQ_WORKSPACE", "runtime/projects"))
SOURCE_STORE = ImmutableSourceStore(Path(os.environ.get("BUILDCOSTIQ_SOURCE_STORE", "runtime/sources")))
AUTH_STORE = LocalAuthStore(os.environ.get("BUILDCOSTIQ_AUTH", "runtime/auth"))
SESSIONS: dict[str, dict[str, Any]] = {}

RISK_META = {
    "block": {"level": "critical", "label": "紧急阻断", "color": "red", "priority": 3},
    "warn": {"level": "warning", "label": "预警", "color": "yellow", "priority": 2},
    "info": {"level": "notice", "label": "提示", "color": "blue", "priority": 1},
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
            "description": "唯一执行边界，只接受 P01–P08。",
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
            "description": "外部存储与未来集成，不改变 Core。",
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
        {"id": "P01", "label": "合同 intake", "status": "declarative", "surface": "占位能力"},
        {"id": "P02", "label": "工程量清单 intake", "status": "implemented", "surface": "清单输入"},
        {"id": "P03", "label": "图纸 intake", "status": "declarative", "surface": "占位能力"},
        {"id": "P04", "label": "基线台账", "status": "declarative", "surface": "占位能力"},
        {"id": "P05", "label": "成本计划", "status": "implemented", "surface": "成本计划"},
        {"id": "P06", "label": "变更管理", "status": "declarative", "surface": "占位能力"},
        {"id": "P07", "label": "证据关联", "status": "declarative", "surface": "占位能力"},
        {"id": "P08", "label": "结算初审", "status": "implemented", "surface": "当前工作面"},
    ],
    "shared_modules": [
        {"label": "plugins/normalize.py", "description": "单位归一化与换算，纯 helper，不注册 Gateway。"},
        {"label": "plugins/basis.py", "description": "价格口径可比性，冲突时不输出偏差数。"},
    ],
    "invariants": [
        "Core 不反向依赖业务插件或外部适配器。",
        "GUI / adapters / plugins → Core。",
        "冻结范围之外的新增 capability 在本版本被拒绝。",
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
    return SESSIONS.get(token)


def _require_actor(headers: Mapping[str, str], permission: str | None = None) -> dict[str, Any]:
    actor = _optional_actor(headers)
    if actor is None:
        raise PermissionError("请先登录后再进行此操作")
    if permission and permission not in set(actor.get("permissions", [])):
        raise PermissionError(f"当前角色没有“{permission}”权限")
    return actor


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
    PROJECT_WORKSPACE.add_source(
        project_id,
        {
            "source_id": source_id,
            "document_id": source.id,
            "name": filename,
            "kind": "清单资料",
            "media_type": source.media_type,
            "content_hash": source.content_hash,
            "size": len(content),
        },
    )
    source_metadata = PROJECT_WORKSPACE.load(project_id)["sources"][-1]
    _auto_recognize_source(project_id, source_metadata)
    PROJECT_WORKSPACE.set_stage(project_id, "boq", result)
    if actor:
        PROJECT_WORKSPACE.append_audit(
            project_id,
            "source.uploaded",
            actor,
            source_id,
            {"name": filename, "kind": "清单资料", "item_count": result.get("item_count", 0)},
        )
    return result


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
    filename, content = fields.get("file", ("", b""))
    if not project_id:
        raise ValueError("资料上传缺少项目标识")
    if not filename or not content:
        raise ValueError("请选择项目资料文件")
    source_id = source_id or Path(filename).stem
    source = SOURCE_STORE.ingest(filename, content, mimetypes.guess_type(filename)[0] or "application/octet-stream")
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
        "size": len(content),
    }
    state = PROJECT_WORKSPACE.add_source(project_id, metadata)
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
            "size": len(artifact_content),
        }
    updated_source = {**source, "recognition": result}
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
    return state


def _report_html(state: dict[str, Any]) -> bytes:
    project = state["project"]
    boq = (state.get("boq") or {}).get("result") or {}
    plan = (state.get("cost_plan") or {}).get("result") or {}
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
    body = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{html.escape(str(project['name']))} - 造价工作报告</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:36px;color:#222}}h1{{margin-bottom:6px}}.meta{{color:#666;margin-bottom:24px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #bbb;padding:7px;text-align:left;font-size:12px}}th{{background:#eee}}</style>
</head><body><h1>{html.escape(str(project['name']))} · 造价工作报告</h1>
<div class="meta">项目编号：{html.escape(str(project['id']))}　生成时间：{html.escape(str(project.get('updated_at', '')))}</div>
<h2>工作状态</h2><p style="font-size:18px;font-weight:bold;color:{gate_color}">结算初审：{gate}</p>
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
                    "size": len(raw),
                }
            )
    return PROJECT_WORKSPACE.save(state)


def _health() -> dict[str, Any]:
    return {
        "service": "BuildCostIQ WebUI",
        "runtime": RUNTIME.health(),
        "review_capability": "P08",
        "business_capabilities": ["P02", "P05", "P08"],
        "dependencies": {"external_runtime": False, "project_dependency": "openpyxl+pypdf+markitdown"},
        "privacy": {"default_mode": "local_only", "external_send": "explicit_consent_required"},
        "release_highlights": "文件查看、权限分级与审计留痕、项目经理和造价人员双工作台、风险颜色与预警标注",
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
    server_version = "BuildCostIQWebUI/0.1"

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
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _write_inline(self, body: bytes, content_type: str, filename: str) -> None:
        safe_name = Path(filename).name.replace('"', "") or "source.bin"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
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
        elif path == "/api/health":
            self._write_json(_health())
        elif path == "/api/architecture":
            self._write_json(_architecture())
        elif path == "/api/sample":
            self._write_json(DEMO_REQUEST)
        elif path == "/api/connectors":
            self._write_json({"connectors": connector_catalog()})
        elif path == "/api/recognition/catalog":
            self._write_json({"recognizers": recognition_catalog()})
        elif path == "/api/audit":
            try:
                _require_actor(self.headers, "view_audit")
                project_id = parse_qs(parsed.query).get("project_id", [""])[0]
                state = _workspace(project_id)
                self._write_json({"audit_log": state.get("audit_log") or []})
            except PermissionError as exc:
                self._write_json({"error": str(exc)}, 401)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path == "/api/workspace":
            project_id = parse_qs(parsed.query).get("project_id", [""])[0]
            try:
                self._write_json(_workspace(project_id))
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
        elif path.startswith("/api/workspace/"):
            project_id = unquote(path.removeprefix("/api/workspace/").split("/", 1)[0])
            try:
                state = _workspace(project_id)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
                return
            if path.endswith("/report"):
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
                self._write_download(_cost_plan_csv(state), "text/csv; charset=utf-8", "cost-plan.csv")
            elif path.endswith("/cost-plan.xlsx"):
                self._write_download(
                    _cost_plan_xlsx(state),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "cost-plan.xlsx",
                )
            elif path.endswith("/bundle"):
                self._write_download(
                    _project_bundle(state),
                    "application/zip",
                    f"{state['project']['id']}-buildcostiq.zip",
                )
            else:
                self._write_json(state)
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
                self._write_json(_project(self._read_json(), _optional_actor(self.headers)))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            return
        if path == "/api/source/upload":
            try:
                self._write_json(_source_upload(self.headers.get("Content-Type", ""), self._read_body(), _optional_actor(self.headers)))
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/source/recognize":
            try:
                self._write_json(_recognize_source(self._read_json(), _optional_actor(self.headers)))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except FileNotFoundError as exc:
                self._write_json({"error": str(exc)}, 404)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/workspace/import":
            try:
                self._write_json(_import_project_bundle(self.headers.get("Content-Type", ""), self._read_body()))
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
            return
        if path == "/api/boq/upload":
            try:
                result = _boq_upload(self.headers.get("Content-Type", ""), self._read_body(), _optional_actor(self.headers))
            except (UnicodeDecodeError, ValueError) as exc:
                self._write_json({"error": str(exc)}, 422)
                return
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                self._write_json({"error": str(exc)}, 500)
                return
            self._write_json(result)
            return

        actor = _optional_actor(self.headers)
        handlers = {
            "/api/boq": lambda payload: _boq(payload, actor),
            "/api/cost-plan": lambda payload: _cost_plan(payload, actor),
            "/api/review": lambda payload: _review(payload, actor),
        }
        handler = handlers.get(urlsplit(self.path).path)
        if handler is None:
            self._write_json({"error": "Not found"}, 404)
            return
        try:
            result = handler(self._read_json())
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._write_json({"error": str(exc)}, 422)
            return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._write_json({"error": str(exc)}, 500)
            return
        self._write_json(result)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[webui] {self.address_string()} - {format % args}")


def create_server(host: str = "127.0.0.1", port: int = 8787) -> BuildCostWebServer:
    return BuildCostWebServer((host, port), BuildCostHandler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the local BuildCostIQ WebUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    print(f"BuildCostIQ WebUI: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
