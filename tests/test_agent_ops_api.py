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
from gui import server as server_module
from gui.server import create_server


class AgentOpsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_config = server_module.DEPLOYMENT_CONFIG
        self.temp_dir = tempfile.TemporaryDirectory()
        roots = StorageRoots.from_environment({"BUILDCOSTIQ_DATA_ROOT": str(Path(self.temp_dir.name) / "data")})
        config = DeploymentConfig(mode="single-node", node_id="agent-ops-test", host="127.0.0.1", port=0, roots=roots)
        server_module._configure_deployment(config)
        self.server = create_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.tokens: list[str] = []
        manager = self._register("cost-manager", "cost_manager")
        self.manager_token = manager["token"]
        self.manager_id = manager["user"]["id"]
        self.project_id = f"agent-ops-{uuid4().hex[:10]}"
        self._post("/api/project", {"project_id": self.project_id, "name": "Agent Ops 合成项目"}, self.manager_token)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        for token in self.tokens:
            server_module.SESSIONS.pop(token, None)
        server_module._configure_deployment(self.previous_config)
        self.temp_dir.cleanup()

    def _register(self, prefix: str, role: str) -> dict:
        username = f"{prefix}-{uuid4().hex[:8]}"
        request = Request(
            f"{self.base_url}/api/auth/register",
            data=json.dumps({"username": username, "password": "Local-test-123", "role": role}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.tokens.append(result["token"])
        return result

    def _post(self, path: str, payload: dict, token: str | None) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers=headers,
            method="POST",
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)
        with response:
            return response.status, json.load(response)

    def _plan(self, **updates) -> dict:
        payload = {
            "project_id": self.project_id,
            "run_id": "run-agent-01",
            "workflow_id": "WF02",
            "module_id": "02",
            "target_type": "workflow_plan",
            "target_id": "bid-preparation",
            "payload_summary": "投标工作流计划已就绪",
            "idempotency_key": "plan-v1",
            "agent_ops_state": "READY",
        }
        payload.update(updates)
        return payload

    def test_authenticated_plan_record_is_project_scoped_idempotent_and_plan_only(self) -> None:
        status, first = self._post("/api/agent-ops/plan", self._plan(), self.manager_token)
        self.assertEqual(201, status)
        event = first["event"]
        self.assertEqual(self.manager_id, event["actor_id"])
        self.assertEqual("human", event["actor_type"])
        self.assertEqual("candidate", event["record_authority"])
        self.assertEqual("plan_ready_only", event["agent_ops_state_meaning"])

        status, retry = self._post("/api/agent-ops/plan", self._plan(), self.manager_token)
        self.assertEqual(201, status)
        self.assertEqual(event["event_id"], retry["event"]["event_id"])

        request = Request(
            f"{self.base_url}/api/agent-ops/ledger?project_id={self.project_id}",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        with urlopen(request, timeout=2) as response:
            ledger = json.load(response)
        self.assertTrue(ledger["verification"]["valid"])
        self.assertEqual(1, ledger["verification"]["event_count"])
        self.assertEqual(event["event_hash"], ledger["events"][0]["event_hash"])
        self.assertEqual(1, len(ledger["agent_ops_plan_states"]))
        self.assertEqual("READY", ledger["agent_ops_plan_states"][0]["state"])
        self.assertEqual("plan_ready_only", ledger["agent_ops_plan_states"][0]["state_meaning"])

    def test_identity_permission_and_membership_cannot_be_supplied_by_request(self) -> None:
        status, _ = self._post("/api/agent-ops/plan", self._plan(actor_id="forged-user"), self.manager_token)
        self.assertEqual(422, status)

        project_manager = self._register("project-manager", "project_manager")
        server_module.AUTH_STORE.add_user_to_project(self.project_id, project_manager["user"]["id"])
        status, _ = self._post("/api/agent-ops/plan", self._plan(), project_manager["token"])
        self.assertEqual(403, status)

        non_member = self._register("non-member", "cost_manager")
        status, _ = self._post("/api/agent-ops/plan", self._plan(), non_member["token"])
        self.assertEqual(403, status)
        self.assertEqual(0, server_module.PROJECT_WORKSPACE.verify_execution_ledger(self.project_id)["event_count"])

    def test_agent_ops_role_suggestion_is_local_project_scoped_and_never_grants_access(self) -> None:
        project_manager = self._register("role-project-manager", "project_manager")
        server_module.AUTH_STORE.add_user_to_project(self.project_id, project_manager["user"]["id"])
        payload = {
            "project_id": self.project_id,
            "job_title": "实验员",
            "responsibilities": "负责混凝土试件取样送检和试验报告",
        }
        users_before = server_module.AUTH_STORE.list_public_users()
        status, result = self._post("/api/agent-ops/role-assignment", payload, project_manager["token"])
        self.assertEqual(200, status)
        self.assertEqual("sayelf-agent-ops-local", result["source"])
        self.assertTrue(result["human_confirmation_required"])
        self.assertFalse(result["input_persisted"])
        self.assertEqual("MATCHED", result["recommendation"]["status"])
        self.assertEqual("lab_testing_officer", result["recommendation"]["recommended_role"])
        self.assertNotIn("responsibilities", result)
        self.assertNotIn("负责混凝土试件取样送检和试验报告", json.dumps(result, ensure_ascii=False))
        lab_role = next(item for item in result["role_options"] if item["role"] == "lab_testing_officer")
        catalog_lab_role = next(item for item in server_module.AUTH_STORE.personnel_role_catalog() if item["role"] == "lab_testing_officer")
        self.assertEqual(
            {item["key"] for item in catalog_lab_role["permissions"]},
            {item["key"] for item in lab_role["permissions"]},
        )
        self.assertEqual(len(users_before), len(server_module.AUTH_STORE.list_public_users()))

        conflict_payload = {**payload, "job_title": "施工员", "responsibilities": "负责技术方案审核"}
        status, conflict = self._post("/api/agent-ops/role-assignment", conflict_payload, project_manager["token"])
        self.assertEqual(200, status)
        self.assertEqual("NEEDS_REVIEW", conflict["recommendation"]["status"])
        self.assertEqual("", conflict["recommendation"]["recommended_role"])

        status, _ = self._post("/api/agent-ops/role-assignment", payload, self.manager_token)
        self.assertEqual(403, status)
        non_member = self._register("role-non-member", "project_manager")
        status, _ = self._post("/api/agent-ops/role-assignment", payload, non_member["token"])
        self.assertEqual(403, status)

        status, _ = self._post(
            "/api/agent-ops/role-assignment",
            {**payload, "username": "must-not-be-accepted"},
            project_manager["token"],
        )
        self.assertEqual(422, status)

    def test_plan_api_rejects_unresolved_evidence_without_persisting_it(self) -> None:
        digest = "e" * 64
        server_module.PROJECT_WORKSPACE.add_source(
            self.project_id,
            {"source_id": "api-source", "content_hash": digest, "status": "active"},
        )
        status, accepted = self._post(
            "/api/agent-ops/plan",
            self._plan(evidence_refs=[f"sha256:{digest}"]),
            self.manager_token,
        )
        self.assertEqual(201, status)
        self.assertEqual([f"sha256:{digest}"], accepted["event"]["evidence_refs"])

        status, _ = self._post(
            "/api/agent-ops/plan",
            self._plan(idempotency_key="unknown-evidence", evidence_refs=[f"sha256:{'f' * 64}"]),
            self.manager_token,
        )
        self.assertEqual(422, status)
        self.assertEqual(1, server_module.PROJECT_WORKSPACE.verify_execution_ledger(self.project_id)["event_count"])

    def test_corrupt_ledger_is_rejected_for_read_and_further_append(self) -> None:
        status, _ = self._post("/api/agent-ops/plan", self._plan(), self.manager_token)
        self.assertEqual(201, status)
        state = server_module.PROJECT_WORKSPACE.load(self.project_id)
        state["execution_ledger"][0]["payload_summary"] = "本地篡改"
        server_module.PROJECT_WORKSPACE.save(state)

        request = Request(
            f"{self.base_url}/api/agent-ops/ledger?project_id={self.project_id}",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        try:
            with urlopen(request, timeout=2):
                self.fail("A damaged ledger must not be returned")
        except HTTPError as error:
            with error:
                self.assertEqual(422, error.code)

        status, _ = self._post("/api/agent-ops/plan", self._plan(idempotency_key="plan-v2"), self.manager_token)
        self.assertEqual(422, status)


if __name__ == "__main__":
    unittest.main()
