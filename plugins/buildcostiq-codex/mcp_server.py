"""BuildCostIQ's dependency-free local MCP stdio bridge.

The bridge deliberately lives outside Core and P01–P09.  It only projects the
existing workspace, role contracts, permissions, and P09 read model into MCP
tools.  MCP JSON-RPC is newline-delimited on stdin/stdout; diagnostics go to
stderr so a client never receives a non-protocol byte.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


SERVER_NAME = "buildcostiq-codex"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", PROTOCOL_VERSION}


def _project_root() -> Path:
    configured = os.environ.get("BUILDCOSTIQ_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").exists() and (parent / "core").is_dir():
            return parent
    raise RuntimeError("无法定位 BuildCostIQ 项目根目录，请设置 BUILDCOSTIQ_PROJECT_ROOT")


PROJECT_ROOT = _project_root()
# Relative runtime roots must be interpreted like the WebUI, from the repo
# root, rather than from this plugin directory.
os.chdir(PROJECT_ROOT)
if not os.environ.get("BUILDCOSTIQ_DATA_ROOT"):
    os.environ["BUILDCOSTIQ_DATA_ROOT"] = str(PROJECT_ROOT / "runtime")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters import (  # noqa: E402  (bootstrap must run first)
    DeploymentConfig,
    LocalAuthStore,
    LocalProjectWorkspace,
    role_workbench_contracts,
)


def _server_module():
    """Load the existing WebUI service boundary lazily and exactly once."""

    import gui.server as server

    return server


AUTH_STORE = LocalAuthStore(DeploymentConfig.from_environment().roots.auth)
WORKSPACE = LocalProjectWorkspace(
    DeploymentConfig.from_environment().roots.projects,
)


class BridgeError(RuntimeError):
    """A safe, user-facing MCP error (never a traceback)."""


def _actor(*, required: bool = True) -> dict[str, Any]:
    configured = os.environ.get("BUILDCOSTIQ_MCP_ACTOR", "").strip()
    if not configured:
        if required:
            raise BridgeError(
                "本地 MCP 未配置岗位身份。请设置 BUILDCOSTIQ_MCP_ACTOR（用户 id 或登录名），"
                "再访问项目数据；公开岗位契约无需身份。"
            )
        return {
            "id": "local-mcp",
            "username": "local-mcp",
            "display_name": "Local MCP",
            "role": "anonymous",
            "roles": [],
            "permissions": ["view_workspace"],
        }
    users = AUTH_STORE.list_public_users()
    actor = next(
        (
            user
            for user in users
            if configured.lower()
            in {
                str(user.get("id", "")).lower(),
                str(user.get("username", "")).lower(),
                str(user.get("display_name", "")).lower(),
            }
        ),
        None,
    )
    if actor is None:
        raise BridgeError("BUILDCOSTIQ_MCP_ACTOR 不对应本地已登记人员；不会在 MCP 中伪造岗位身份")
    return actor


def _require_permission(actor: Mapping[str, Any], permission: str) -> None:
    if permission not in set(actor.get("permissions", [])):
        raise BridgeError(f"当前岗位没有 {permission} 权限；请通过 WebUI 使用正确的岗位账号")


def _require_project(project_id: str, actor: Mapping[str, Any]) -> dict[str, Any]:
    project_id = str(project_id or "").strip()
    if not project_id:
        raise BridgeError("缺少 project_id")
    _require_permission(actor, "view_workspace")
    state = WORKSPACE.load(project_id)
    if state is None:
        raise BridgeError("项目不存在；MCP 不会自动创建未治理项目")
    member_ids = set(AUTH_STORE.ensure_project_membership(project_id))
    if str(actor.get("id")) not in member_ids:
        raise BridgeError("当前人员不属于该项目；请由项目经理在 WebUI 中维护项目人员")
    return state


def _tool_get_role_workbench(arguments: Mapping[str, Any]) -> dict[str, Any]:
    role = str(arguments.get("role", "")).strip()
    contracts = role_workbench_contracts()
    if role:
        role_contract = contracts.get("roles", {}).get(role)
        if role_contract is None:
            raise BridgeError("未知岗位；请先读取 line contracts 或使用现有岗位代码")
        return {"role": role, "contract": role_contract, "policy": contracts.get("policy", {})}
    return contracts


def _tool_get_line_contracts(_: Mapping[str, Any]) -> dict[str, Any]:
    server = _server_module()
    return server._line_contracts()


def _tool_get_workspace_snapshot(arguments: Mapping[str, Any]) -> dict[str, Any]:
    actor = _actor()
    state = _require_project(str(arguments.get("project_id", "")), actor)
    server = _server_module()
    visible = server._visible_workspace(state, actor)
    return {
        "workspace": visible,
        "role_work_products": server._role_work_products_response(state, actor),
        "p09": server._p09_result(state) if "p09" in server._workspace_views_for_actor(actor) else None,
        "webui": {"url": "http://127.0.0.1:8787/", "read_only_preview": True},
    }


def _tool_get_role_work_products(arguments: Mapping[str, Any]) -> dict[str, Any]:
    actor = _actor()
    state = _require_project(str(arguments.get("project_id", "")), actor)
    return _server_module()._role_work_products_response(state, actor)


def _tool_submit_role_work_product(arguments: Mapping[str, Any]) -> dict[str, Any]:
    if arguments.get("confirm") is not True:
        raise BridgeError("保存岗位成果会写入项目状态；请先向用户展示字段和交接对象，并在确认后传入 confirm=true")
    actor = _actor()
    project_id = str(arguments.get("project_id", ""))
    _require_project(project_id, actor)
    _require_permission(actor, "edit_business_data")
    role = str(arguments.get("role") or actor.get("role") or "").strip()
    actor_roles = set(str(item) for item in actor.get("roles", []) or [])
    if not actor_roles:
        actor_roles = {str(actor.get("role", ""))}
    if role not in actor_roles:
        raise BridgeError("只能保存当前登录岗位的工作成果；施工员/测量员合并仍须使用已登记的岗位组合")
    payload = {
        "project_id": project_id,
        "role": role,
        "fields": arguments.get("fields", {}),
        "handoff_to": arguments.get("handoff_to", []),
        "event_id": arguments.get("event_id", ""),
        "evidence_refs": arguments.get("evidence_refs", []),
        "source_refs": arguments.get("source_refs", []),
        "collaboration_note": arguments.get("collaboration_note", ""),
        "status": arguments.get("status", "SUBMITTED"),
    }
    return _server_module()._role_work_product_create(payload, actor)


def _tool_get_p09_summary(arguments: Mapping[str, Any]) -> dict[str, Any]:
    actor = _actor()
    state = _require_project(str(arguments.get("project_id", "")), actor)
    server = _server_module()
    if "p09" not in server._workspace_views_for_actor(actor):
        raise BridgeError("P09 成果经营只对项目经理和造价经理开放")
    return {
        "project_id": str(arguments.get("project_id", "")),
        "p09": server._p09_result(state),
        "policy": {
            "derived_from": ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "Core Event"],
            "second_amount_ledger": False,
            "decision_is_human": True,
        },
    }


def _tool_health(_: Mapping[str, Any]) -> dict[str, Any]:
    config = DeploymentConfig.from_environment()
    return {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "project_root": str(PROJECT_ROOT),
        "deployment": config.public(include_paths=False),
        "webui": {"url": f"http://{config.host}:{config.port}/"},
        "api_key_required": False,
        "data_boundary": "复用现有 Core、P01–P09、权限与部署/存储适配层",
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "buildcostiq_health",
        "description": "检查本地 BuildCostIQ、部署存储边界和 WebUI 地址；不读取业务详情。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "buildcostiq_get_role_workbench_contract",
        "description": "读取一个岗位或全部岗位的输入字段、工作成果、交接对象和 Core/P01–P09 映射。",
        "inputSchema": {"type": "object", "properties": {"role": {"type": "string"}}, "additionalProperties": False},
    },
    {
        "name": "buildcostiq_get_line_contracts",
        "description": "读取生产线、技术线、造价线和岗位协同契约；只读，不创建第二金额事实源。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "buildcostiq_get_workspace_snapshot",
        "description": "按当前登录岗位返回一个项目的可见工作面、成果交接、P09 派生视图和 WebUI 入口。",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buildcostiq_get_role_work_products",
        "description": "只读当前岗位自己的岗位成果及交接给自己的成果，遵守现有岗位权限。",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buildcostiq_submit_role_work_product",
        "description": "在用户明确确认后保存一个岗位成果，并关联 Event、Evidence、Source 和交接对象。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "role": {"type": "string"},
                "fields": {"type": "object"},
                "handoff_to": {"type": "array", "items": {"type": "string"}},
                "event_id": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "source_refs": {"type": "array", "items": {"type": "string"}},
                "collaboration_note": {"type": "string"},
                "status": {"type": "string"},
                "confirm": {"type": "boolean"}
            },
            "required": ["project_id", "fields", "confirm"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buildcostiq_get_p09_summary",
        "description": "读取项目经理或造价经理可见的 P09 成果经营派生摘要；不建立第二金额账。",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
]


DISPATCH = {
    "buildcostiq_health": _tool_health,
    "buildcostiq_get_role_workbench_contract": _tool_get_role_workbench,
    "buildcostiq_get_line_contracts": _tool_get_line_contracts,
    "buildcostiq_get_workspace_snapshot": _tool_get_workspace_snapshot,
    "buildcostiq_get_role_work_products": _tool_get_role_work_products,
    "buildcostiq_submit_role_work_product": _tool_submit_role_work_product,
    "buildcostiq_get_p09_summary": _tool_get_p09_summary,
}


def _rpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    """Return a normal JSON-RPC result (initialize/list/ping)."""

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _tool_result(request_id: Any, result: Any) -> dict[str, Any]:
    """Return the MCP tool-call content envelope."""

    structured = result if isinstance(result, dict) else {"value": result}
    text = json.dumps(structured, ensure_ascii=False, default=str)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": structured,
        },
    }


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: Mapping[str, Any]) -> dict[str, Any] | None:
    method = str(request.get("method", ""))
    request_id = request.get("id")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
        requested_version = str(params.get("protocolVersion", "")).strip()
        protocol_version = requested_version if requested_version in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
        return _rpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "先读取岗位契约，再读取当前岗位可见工作面；所有写入必须由用户确认。",
            },
        )
    if method == "ping":
        return _rpc_result(request_id, {})
    if method == "tools/list":
        return _rpc_result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
        name = str(params.get("name", ""))
        arguments = params.get("arguments") if isinstance(params.get("arguments"), Mapping) else {}
        func = DISPATCH.get(name)
        if func is None:
            return _error(request_id, -32601, f"未知工具: {name}")
        try:
            return _tool_result(request_id, func(arguments))
        except (BridgeError, PermissionError, FileNotFoundError, ValueError) as exc:
            return _error(request_id, -32001, str(exc))
        except Exception as exc:  # pragma: no cover - last-resort protocol safety
            print(f"{SERVER_NAME}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return _error(request_id, -32603, "本地 MCP 执行失败；详情已写入 stderr")
    return _error(request_id, -32601, f"不支持的 MCP 方法: {method}")


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, Mapping):
                raise ValueError("请求必须是 JSON 对象")
            response = handle(request)
        except Exception as exc:
            request_id = None
            try:
                request_id = json.loads(raw).get("id")
            except Exception:
                pass
            response = _error(request_id, -32700, f"无效 JSON-RPC 请求: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
