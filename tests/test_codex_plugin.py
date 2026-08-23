from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "buildcostiq-codex"


def _mcp(*requests: dict[str, object]) -> list[dict[str, object]]:
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests)
    env = {**os.environ, "BUILDCOSTIQ_PROJECT_ROOT": str(ROOT)}
    completed = subprocess.run(
        [sys.executable, "-u", str(PLUGIN / "mcp_server.py")],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        check=True,
        timeout=20,
    )
    assert completed.stderr == "", completed.stderr
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def test_plugin_manifest_and_skill_are_present() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "buildcostiq-codex"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert "P01–P09" in (PLUGIN / "skills" / "municipal-cost-workflow" / "SKILL.md").read_text(encoding="utf-8")


def test_mcp_initialize_health_and_tools_list() -> None:
    responses = _mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "buildcostiq_health", "arguments": {}}},
    )
    assert responses[0]["result"]["serverInfo"]["name"] == "buildcostiq-codex"
    tool_names = {item["name"] for item in responses[1]["result"]["tools"]}
    assert "buildcostiq_submit_role_work_product" in tool_names
    health = responses[2]["result"]["structuredContent"]
    assert health["api_key_required"] is False
    assert health["webui"]["url"].endswith(":8787/")


def test_mcp_role_contract_is_public_and_writes_require_confirmation() -> None:
    responses = _mcp(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "buildcostiq_get_role_workbench_contract", "arguments": {"role": "warehouse_officer"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "buildcostiq_submit_role_work_product",
                "arguments": {"project_id": "demo", "fields": {}, "confirm": False},
            },
        },
    )
    contract = responses[0]["result"]["structuredContent"]
    assert contract["role"] == "warehouse_officer"
    assert "contract" in contract
    assert responses[1]["error"]["code"] == -32001
    assert "confirm=true" in responses[1]["error"]["message"]
