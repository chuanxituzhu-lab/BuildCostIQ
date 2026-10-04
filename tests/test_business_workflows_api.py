from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from adapters.deployment import DeploymentConfig, StorageRoots
from domains.business_workflows import MODULES
from gui import server as server_module
from gui.server import create_server


class BusinessWorkflowApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_config = server_module.DEPLOYMENT_CONFIG
        self.temp_dir = tempfile.TemporaryDirectory()
        roots = StorageRoots.from_environment({"BUILDCOSTIQ_DATA_ROOT": str(Path(self.temp_dir.name) / "data")})
        server_module._configure_deployment(DeploymentConfig(mode="single-node", node_id="workflow-test", host="127.0.0.1", port=0, roots=roots))
        self.server = create_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.tokens: list[str] = []
        self.manager = self._register("manager", "cost_manager")
        self.project_id = f"workflow-{uuid4().hex[:10]}"
        self._post("/api/project", {"project_id": self.project_id, "name": "流程 API 合成项目"}, self.manager["token"])
        source = server_module.SOURCE_STORE.ingest("workflow-evidence.pdf", b"synthetic test evidence", "application/pdf")
        server_module.PROJECT_WORKSPACE.add_source(self.project_id, {"source_id": source.id, "name": source.name, "content_hash": source.content_hash, "status": "active"})
        self.evidence = [f"sha256:{source.content_hash}"]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        for token in self.tokens:
            server_module.SESSIONS.pop(token, None)
        server_module._configure_deployment(self.previous_config)
        self.temp_dir.cleanup()

    def _register(self, prefix: str, role: str) -> dict:
        request = Request(f"{self.base_url}/api/auth/register", data=json.dumps({"username": f"{prefix}-{uuid4().hex[:8]}", "password": "Local-test-123", "role": role}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        self.tokens.append(result["token"])
        return result

    def _request(self, method: str, path: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def _post(self, path: str, payload: dict, token: str | None) -> tuple[int, dict]:
        return self._request("POST", path, payload, token)

    def test_project_scoped_chinese_workflow_api_enforces_human_role_gate(self) -> None:
        status, catalog = self._request("GET", f"/api/business-workflows?project_id={self.project_id}", token=self.manager["token"])
        self.assertEqual(200, status)
        self.assertEqual(8, len(catalog["modules"]))
        self.assertTrue(catalog["recovery"]["status"] == "replayed")

        fields = {item["key"]: ("2026-10-04" if item["kind"] == "date" else "1" if item["kind"] == "decimal" else f"合成-{item['key']}") for item in MODULES["01"]["fields"]}
        status, created = self._post("/api/business-workflows", {"project_id": self.project_id, "action": "create", "module_id": "01", "fields": fields, "evidence_refs": self.evidence, "idempotency_key": "api-create-01"}, self.manager["token"])
        self.assertEqual(200, status)
        run = created["runs"][0]
        self.assertEqual("draft", run["status"])
        self.assertIn("01", run["run_id"])

        status, submitted = self._post("/api/business-workflows", {"project_id": self.project_id, "action": "submit", "module_id": "01", "run_id": run["run_id"], "idempotency_key": "api-submit-01"}, self.manager["token"])
        self.assertEqual(200, status)
        step = MODULES["01"]["steps"][0]
        status, self_approval = self._post("/api/business-workflows", {"project_id": self.project_id, "action": "decide", "module_id": "01", "run_id": run["run_id"], "step": step["key"], "decision": "approve", "checklist": {key: True for key in step["checks"]}, "evidence_refs": self.evidence, "idempotency_key": "api-self-approve"}, self.manager["token"])
        self.assertEqual(422, status)
        self.assertIn("不能重复审批/验收", self_approval["error"])

        reviewer = self._register("reviewer", "cost_manager")
        server_module.AUTH_STORE.add_user_to_project(self.project_id, reviewer["user"]["id"])
        status, reviewed = self._post("/api/business-workflows", {"project_id": self.project_id, "action": "decide", "module_id": "01", "run_id": run["run_id"], "step": step["key"], "decision": "approve", "checklist": {key: True for key in step["checks"]}, "evidence_refs": self.evidence, "idempotency_key": "api-review-01"}, reviewer["token"])
        self.assertEqual(200, status)
        updated = next(item for item in reviewed["runs"] if item["run_id"] == run["run_id"])
        self.assertEqual("basis_acceptance", updated["current_step"])
        self.assertEqual("READY", updated["agent_ops_plan"]["state"])

        outsider = self._register("outsider", "cost_manager")
        status, _ = self._request("GET", f"/api/business-workflows?project_id={self.project_id}", token=outsider["token"])
        self.assertEqual(403, status)


if __name__ == "__main__":
    unittest.main()
