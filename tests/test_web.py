from __future__ import annotations

import io
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile

from gui.server import create_server


class WebUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = create_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        suffix = uuid4().hex[:10]
        request = Request(
            f"{self.base_url}/api/auth/register",
            data=json.dumps({"username": f"cost-manager-{suffix}", "password": "local-pass", "role": "cost_manager"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            self.manager_token = json.load(response)["token"]

    def auth_headers(self, content_type: str | None = None, token: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {token or self.manager_token}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def auth_request(self, path: str, token: str | None = None) -> Request:
        return Request(f"{self.base_url}{path}", headers=self.auth_headers(token=token))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_serves_workbench_and_health(self):
        with urlopen(f"{self.base_url}/", timeout=2) as response:
            body = response.read().decode("utf-8")
        self.assertIn("BuildCostIQ", body)
        self.assertNotIn("JSON", body)
        self.assertIn("清单资料", body)
        self.assertIn('id="fileInput"', body)
        self.assertIn('id="projectInfoInput"', body)
        self.assertIn("multiple", body)
        self.assertIn(".pdf", body)
        self.assertIn('id="loginForm"', body)
        self.assertIn('id="personnelTab"', body)
        self.assertIn("项目经理工作台", body)
        self.assertIn("经营看板", body)

        with urlopen(f"{self.base_url}/api/health", timeout=2) as response:
            health = json.load(response)
        self.assertEqual(health["review_capability"], "P08")
        self.assertEqual(health["runtime"]["capabilities"], [f"P{i:02d}" for i in range(1, 9)])

        with urlopen(f"{self.base_url}/api/architecture", timeout=2) as response:
            architecture = json.load(response)
        self.assertEqual(architecture["registered"], [f"P{i:02d}" for i in range(1, 9)])
        self.assertEqual(architecture["capabilities"][-1]["id"], "P08")
        self.assertEqual(architecture["capabilities"][-1]["status"], "implemented")
        self.assertTrue(any(layer["id"] == "gateway" for layer in architecture["layers"]))

    def test_local_roles_control_source_lifecycle_and_audit(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token=""):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        estimator = post_json("/api/auth/register", {"username": f"est-{suffix}", "password": "local-pass", "role": "cost_estimator"})
        manager = post_json("/api/auth/register", {"username": f"mgr-{suffix}", "password": "local-pass", "role": "cost_manager"})
        estimator_token = estimator["token"]
        manager_token = manager["token"]
        project_id = f"audit-project-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "审计权限测试项目"}, estimator_token)

        boundary = f"----BuildCostIQAudit{suffix}"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="project_id"\r\n\r\n'
            f"{project_id}\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_id"\r\n\r\nsource-audit\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="ledger.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "local ledger\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        upload_request = Request(
            f"{self.base_url}/api/source/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Authorization": f"Bearer {estimator_token}"},
            method="POST",
        )
        with urlopen(upload_request, timeout=2) as response:
            uploaded = json.load(response)
        self.assertEqual(uploaded["source"]["source_id"], "source-audit")
        self.assertEqual(uploaded["source"]["archive_area"], "项目资料库/待分类")
        self.assertIn("archive_path", uploaded["source"])

        view_request = Request(
            f"{self.base_url}/api/source/view?project_id={project_id}&source_id=source-audit",
            headers={"Authorization": f"Bearer {estimator_token}"},
        )
        with urlopen(view_request, timeout=2) as response:
            self.assertEqual(response.read(), b"local ledger")

        modified = post_json(
            "/api/source/modify",
            {"project_id": project_id, "source_id": "source-audit", "changes": {"name": "ledger-renamed.txt"}},
            estimator_token,
        )
        self.assertEqual(modified["source"]["name"], "ledger-renamed.txt")
        with self.assertRaises(HTTPError) as denied:
            post_json("/api/source/delete", {"project_id": project_id, "source_id": "source-audit"}, estimator_token)
        self.assertEqual(denied.exception.code, 403)

        deleted = post_json("/api/source/delete", {"project_id": project_id, "source_id": "source-audit"}, manager_token)
        self.assertEqual(deleted["source"]["status"], "deleted")
        audit_request = Request(
            f"{self.base_url}/api/audit?project_id={project_id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        with urlopen(audit_request, timeout=2) as response:
            actions = [event["action"] for event in json.load(response)["audit_log"]]
        self.assertTrue({"source.uploaded", "source.viewed", "source.modified", "source.deleted"}.issubset(actions))

    def test_three_role_scopes_hide_sensitive_costs_at_api_boundary(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json", token),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        def register(role):
            return post_json("/api/auth/register", {"username": f"{role}-{suffix}", "password": "local-pass", "role": role}, self.manager_token)["token"]

        project_id = f"role-scope-{suffix}"
        manager_token = self.manager_token
        estimator_token = register("cost_estimator")
        project_manager_token = register("project_manager")
        post_json("/api/project", {"project_id": project_id, "name": "角色范围测试项目"}, manager_token)
        post_json(
            "/api/boq",
            {"project_id": project_id, "source_id": "role-source", "rows": [["项目编码", "项目名称", "计量单位", "工程量"], ["0101", "土方", "m3", 10]]},
            manager_token,
        )
        post_json(
            "/api/cost-plan",
            {"project_id": project_id, "source_id": "role-source", "items": [{"code": "0101", "name": "土方", "unit": "m3", "quantity": 10}], "contract_prices": {"0101": 100}},
            manager_token,
        )

        with urlopen(self.auth_request(f"/api/dashboard?project_id={project_id}", project_manager_token), timeout=2) as response:
            project_dashboard = json.load(response)
        self.assertEqual(project_dashboard["audience"], "project_manager")
        self.assertEqual(project_dashboard["access"], "kpi_only")
        self.assertEqual(project_dashboard["comparison"]["rows"], [])
        self.assertEqual(project_dashboard["baseline"]["contract_subtotal"], 1000.0)

        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}", estimator_token), timeout=2) as response:
            estimator_workspace = json.load(response)
        self.assertEqual(estimator_workspace["access"], "operational_redacted")
        self.assertIsNone(estimator_workspace["cost_plan"]["result"]["summary"]["contract_subtotal"])
        self.assertIsNone(estimator_workspace["cost_plan"]["result"]["items"][0]["unit_price"])

        with self.assertRaises(HTTPError) as denied:
            request = Request(
                f"{self.base_url}/api/review",
                data=json.dumps({"project_id": project_id, "source_id": "role-source", "rows": []}).encode("utf-8"),
                headers=self.auth_headers("application/json", estimator_token),
                method="POST",
            )
            urlopen(request, timeout=2)
        self.assertEqual(denied.exception.code, 403)

        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}", manager_token), timeout=2) as response:
            manager_workspace = json.load(response)
        self.assertEqual(manager_workspace["access"], "full")
        self.assertEqual(manager_workspace["cost_plan"]["result"]["summary"]["contract_subtotal"], 1000.0)

    def test_personnel_management_is_available_to_both_managers_only(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json", token),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        def register(role, token):
            return post_json(
                "/api/auth/register",
                {"username": f"personnel-{role}-{suffix}", "password": "local-pass", "role": role},
                token,
            )["token"]

        project_manager_token = register("project_manager", self.manager_token)
        estimator_token = register("cost_estimator", self.manager_token)

        for token in (self.manager_token, project_manager_token):
            with urlopen(self.auth_request("/api/personnel", token), timeout=2) as response:
                snapshot = json.load(response)
            self.assertIn("users", snapshot)
            self.assertIn("audit_log", snapshot)
            self.assertTrue(all("password" not in user for user in snapshot["users"]))

        manager_created = post_json(
            "/api/personnel",
            {"username": f"created-by-cost-manager-{suffix}", "password": "local-pass", "role": "cost_manager"},
            self.manager_token,
        )
        project_manager_created = post_json(
            "/api/personnel",
            {"username": f"created-by-project-manager-{suffix}", "password": "local-pass", "role": "cost_estimator"},
            project_manager_token,
        )
        self.assertTrue(any(user["username"] == f"created-by-cost-manager-{suffix}" for user in manager_created["users"]))
        self.assertTrue(any(user["username"] == f"created-by-project-manager-{suffix}" for user in project_manager_created["users"]))
        self.assertIn("personnel.created", [event["action"] for event in project_manager_created["audit_log"]])

        with self.assertRaises(HTTPError) as denied_get:
            urlopen(self.auth_request("/api/personnel", estimator_token), timeout=2)
        self.assertEqual(denied_get.exception.code, 403)
        with self.assertRaises(HTTPError) as denied_post:
            post_json(
                "/api/personnel",
                {"username": f"denied-{suffix}", "password": "local-pass", "role": "cost_estimator"},
                estimator_token,
            )
        self.assertEqual(denied_post.exception.code, 403)

    def test_external_basis_is_independent_and_can_be_referenced_by_p04(self):
        suffix = uuid4().hex[:10]
        project_id = f"basis-project-{suffix}"

        def post_json(path, payload):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json"),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        post_json("/api/project", {"project_id": project_id, "name": "依据引用测试项目"})
        boundary = f"----BuildCostIQBasis{suffix}"
        parts = [
            ("category", "price_info"),
            ("title", "2026年7月信息价"),
            ("source_org", "本地造价信息站"),
            ("version", "2026-07"),
            ("region", "测试地区"),
            ("effective_from", "2026-07-01"),
            ("effective_to", "2026-07-31"),
        ]
        chunks = []
        for name, value in parts:
            chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"price-info.txt\"\r\n"
            "Content-Type: text/plain\r\n\r\n人材机信息价 2026年7月\r\n"
        )
        chunks.append(f"--{boundary}--\r\n")
        upload_request = Request(
            f"{self.base_url}/api/basis/upload",
            data="".join(chunks).encode("utf-8"),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **self.auth_headers()},
            method="POST",
        )
        with urlopen(upload_request, timeout=2) as response:
            uploaded = json.load(response)
        basis = uploaded["basis"]
        self.assertEqual(basis["category"], "price_info")
        self.assertIn("外部依据库/造价信息", basis["archive_path"])
        self.assertNotIn("content_hash", basis)

        with urlopen(self.auth_request("/api/basis"), timeout=2) as response:
            catalog = json.load(response)
        self.assertTrue(any(item["basis_id"] == basis["basis_id"] for item in catalog["items"]))

        reference = post_json(
            "/api/basis/reference",
            {"project_id": project_id, "basis_id": basis["basis_id"], "stage": "P04"},
        )
        self.assertEqual(reference["basis"]["version"], "2026-07")
        self.assertEqual(reference["workspace"]["basis_references"][0]["stage"], "P04")

        view_request = self.auth_request(f"/api/basis/view?basis_id={basis['basis_id']}")
        with urlopen(view_request, timeout=2) as response:
            self.assertIn("人材机信息价", response.read().decode("utf-8"))

        project_manager_request = Request(
            f"{self.base_url}/api/auth/register",
            data=json.dumps({"username": f"basis-pm-{suffix}", "password": "local-pass", "role": "project_manager"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(project_manager_request, timeout=2) as response:
            project_manager_token = json.load(response)["token"]
        with self.assertRaises(HTTPError) as denied:
            urlopen(self.auth_request("/api/basis", project_manager_token), timeout=2)
        self.assertEqual(denied.exception.code, 403)

    def test_review_endpoint_uses_frozen_gateway(self):
        payload = {
            "project_id": "web-test",
            "source_id": "rows-json",
            "rows": [{
                "row": 1,
                "code": "040202002001",
                "name": "石灰稳定土",
                "unit": "m3",
                "quantity": "10",
                "price": "2.50",
                "total": "25.00",
            }],
        }
        request = Request(
            f"{self.base_url}/api/review",
            data=json.dumps(payload).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["capability_id"], "P08")
        self.assertTrue(result["publishable"])
        self.assertEqual(result["summary"]["row_count"], 1)

    def test_boq_endpoint_uses_p02_gateway(self):
        payload = {
            "project_id": "web-test",
            "source_id": "table-json",
            "rows": [
                ["项目编码", "项目名称", "计量单位", "工程量"],
                ["010502001001", "矩形柱", "m3", 86.4],
            ],
        }
        request = Request(
            f"{self.base_url}/api/boq",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["capability_id"], "P02")
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["items"][0]["code"], "010502001001")

    def test_cost_plan_endpoint_uses_p05_gateway(self):
        payload = {
            "project_id": "web-test",
            "source_id": "table-json",
            "items": [{
                "code": "010502001001",
                "name": "矩形柱",
                "unit": "m3",
                "quantity": 86.4,
            }],
            "contract_prices": {"010502001001": "245.50"},
        }
        request = Request(
            f"{self.base_url}/api/cost-plan",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["capability_id"], "P05")
        self.assertEqual(result["summary"]["contract_item_count"], 1)
        self.assertEqual(result["items"][0]["status"], "contract")

    def test_p01_p03_p04_p06_p07_endpoints_persist_full_workbench(self):
        project_id = f"full-workbench-{uuid4().hex[:10]}"

        def post(path, payload):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json"),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        common = {"project_id": project_id, "source_id": "full-source"}
        self.assertEqual(post("/api/contract", {**common, "contract": {"contract_no": "HT-01", "title": "道路施工", "contract_amount": 1000}, "obligations": [{"name": "提交进度款"}]} )["capability_id"], "P01")
        self.assertEqual(post("/api/drawings", {**common, "drawings": [{"drawing_no": "A-01", "name": "总平面图"}]} )["capability_id"], "P03")
        self.assertEqual(post("/api/baseline", {**common, "entries": [{"name": "土方", "quantity": 10, "unit_price": 2}]} )["capability_id"], "P04")
        self.assertEqual(post("/api/changes", {**common, "changes": [{"title": "材料调整", "amount": 20}]} )["capability_id"], "P06")
        self.assertEqual(post("/api/evidence", {**common, "links": [{"target_type": "change", "target_id": "CH-001"}]} )["capability_id"], "P07")
        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}"), timeout=2) as response:
            workspace = json.load(response)
        self.assertEqual(workspace["contract"]["result"]["capability_id"], "P01")
        self.assertEqual(workspace["drawings"]["result"]["capability_id"], "P03")
        self.assertEqual(workspace["baseline"]["result"]["summary"]["baseline_total"], 20.0)
        self.assertEqual(workspace["changes"]["result"]["summary"]["pending_count"], 1)
        self.assertEqual(workspace["evidence"]["result"]["summary"]["unverified_count"], 1)

    def test_dashboard_summarizes_baseline_alerts_and_periods(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token=""):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        auth = post_json(
            "/api/auth/register",
            {"username": f"dashboard-{suffix}", "password": "local-pass", "role": "cost_manager"},
        )
        token = auth["token"]
        project_id = f"dashboard-project-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "看板预警测试项目"}, token)
        rows = [["项目编码", "项目名称", "计量单位", "工程量"], ["010502001001", "矩形柱", "m3", 10]]
        post_json("/api/boq", {"project_id": project_id, "source_id": "dashboard-source", "rows": rows}, token)
        basis_contract = {
            "tax_inclusion": "tax_inclusive",
            "price_type": "winning_bid",
            "source": "dashboard-contract",
            "price_date": "2026-08",
        }
        basis_market = {
            "tax_inclusion": "tax_inclusive",
            "price_type": "market_quote",
            "source": "dashboard-market",
            "price_date": "2026-08",
        }
        post_json(
            "/api/cost-plan",
            {
                "project_id": project_id,
                "source_id": "dashboard-source",
                "items": [{"code": "010502001001", "name": "矩形柱", "unit": "m3", "quantity": 10}],
                "contract_prices": {"010502001001": 100},
                "market_prices": {"010502001001": 120},
                "contract_basis": basis_contract,
                "market_basis": basis_market,
            },
            token,
        )
        post_json(
            "/api/review",
            {
                "project_id": project_id,
                "source_id": "dashboard-source",
                "rows": [{"row": 1, "code": "010502001001", "name": "矩形柱", "unit": "m3", "quantity": 10, "price": 100, "total": 1000}],
            },
            token,
        )
        request = Request(
            f"{self.base_url}/api/dashboard?project_id={project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urlopen(request, timeout=2) as response:
            dashboard = json.load(response)
        self.assertEqual(dashboard["audience"], "cost_manager")
        self.assertEqual(dashboard["baseline"]["contract_subtotal"], 1000.0)
        self.assertEqual(dashboard["comparison"]["status"], "comparable")
        self.assertEqual(dashboard["comparison"]["over_limit_amount"], 200.0)
        self.assertTrue(any(alert["rule_id"] == "DASH-LIMIT-02" for alert in dashboard["alerts"]))
        self.assertEqual(dashboard["periods"]["week"]["review_count"], 1)
        self.assertEqual(dashboard["periods"]["month"]["issue_count"], 0)

    def test_boq_upload_endpoint_uses_p02_gateway_for_csv(self):
        boundary = "----BuildCostIQTestBoundary"
        parts = [
            ("project_id", "upload-project", None),
            ("source_id", "upload-source", None),
            ("file", "项目编码,项目名称,计量单位,工程量\n010502001001,矩形柱,m3,86.4\n", "boq.csv"),
        ]
        chunks: list[bytes] = []
        for name, value, filename in parts:
            chunks.append(f"--{boundary}\r\n".encode())
            if filename:
                chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
                chunks.append(b"Content-Type: text/csv; charset=utf-8\r\n\r\n")
            else:
                chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(value.encode("utf-8"))
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        request = Request(
            f"{self.base_url}/api/boq/upload",
            data=b"".join(chunks),
            headers=self.auth_headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["capability_id"], "P02")
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["items"][0]["name"], "矩形柱")

    def test_project_workspace_persists_stage_and_exports(self):
        project_id = "workspace-test"
        project_request = Request(
            f"{self.base_url}/api/project",
            data=json.dumps({"project_id": project_id, "name": "工作区测试项目"}, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(project_request, timeout=2) as response:
            project = json.load(response)
        self.assertEqual(project["project"]["name"], "工作区测试项目")

        boq_request = Request(
            f"{self.base_url}/api/boq",
            data=json.dumps({
                "project_id": project_id,
                "source_id": "workspace-boq",
                "rows": [["项目编码", "项目名称", "计量单位", "工程量"], ["010502001001", "矩形柱", "m3", 2]],
            }, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(boq_request, timeout=2):
            pass
        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}"), timeout=2) as response:
            workspace = json.load(response)
        self.assertEqual(workspace["project"]["name"], "工作区测试项目")
        self.assertEqual(workspace["boq"]["result"]["item_count"], 1)

        with urlopen(self.auth_request(f"/api/workspace/{project_id}/report"), timeout=2) as response:
            report = response.read().decode("utf-8")
        self.assertIn("工作区测试项目", report)
        with urlopen(self.auth_request(f"/api/workspace/{project_id}/cost-plan.csv"), timeout=2) as response:
            csv_body = response.read().decode("utf-8-sig")
        self.assertIn("项目编码", csv_body)

    def test_generic_source_upload_is_saved_to_project_library(self):
        boundary = "----BuildCostIQSourceBoundary"
        parts = [
            ("project_id", "source-project", None),
            ("source_id", "contract-source", None),
            ("file", b"fake-word-content", "contract.docx"),
        ]
        chunks: list[bytes] = []
        for name, value, filename in parts:
            chunks.append(f"--{boundary}\r\n".encode())
            if filename:
                chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
                chunks.append(b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n")
                chunks.append(value)
            else:
                chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}'.encode())
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        request = Request(
            f"{self.base_url}/api/source/upload",
            data=b"".join(chunks),
            headers=self.auth_headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["source"]["kind"], "Word 文档")
        self.assertEqual(result["workspace"]["sources"][0]["name"], "contract.docx")
        self.assertTrue(Path(result["source"]["storage_path"]).is_file())

    def test_connector_catalog_and_bidirectional_project_exchange(self):
        with urlopen(f"{self.base_url}/api/connectors", timeout=2) as response:
            catalog = json.load(response)["connectors"]
        self.assertEqual({item["id"] for item in catalog}, {"excel-csv", "word-report", "cad-quantity", "budget-software", "project-bundle", "government-basis", "quota-basis", "price-information"})

        project_id = "exchange-test"
        project_request = Request(
            f"{self.base_url}/api/project",
            data=json.dumps({"project_id": project_id, "name": "交换测试项目"}, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(project_request, timeout=2):
            pass
        boq_request = Request(
            f"{self.base_url}/api/boq",
            data=json.dumps({
                "project_id": project_id,
                "source_id": "exchange-boq",
                "rows": [["项目编码", "项目名称", "计量单位", "工程量"], ["010502001001", "矩形柱", "m3", 2]],
            }, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(boq_request, timeout=2):
            pass

        for suffix in ("boq.xlsx", "cost-plan.xlsx"):
            with urlopen(self.auth_request(f"/api/workspace/{project_id}/{suffix}"), timeout=2) as response:
                self.assertEqual(response.read(2), b"PK")

        with urlopen(self.auth_request(f"/api/workspace/{project_id}/bundle"), timeout=2) as response:
            bundle = response.read()
        with ZipFile(io.BytesIO(bundle)) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        self.assertEqual(manifest["format"], "buildcostiq-project-bundle")
        self.assertTrue({"project.json", "boq.csv", "cost-plan.csv", "report.html"}.issubset(names))

        boundary = "----BuildCostIQBundleBoundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="exchange.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + bundle + f"\r\n--{boundary}--\r\n".encode("utf-8")
        import_request = Request(
            f"{self.base_url}/api/workspace/import",
            data=body,
            headers=self.auth_headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urlopen(import_request, timeout=2) as response:
            restored = json.load(response)
        self.assertEqual(restored["project"]["id"], project_id)
        self.assertEqual(restored["boq"]["result"]["item_count"], 1)

    def test_source_recognition_is_local_by_default_and_external_is_gated(self):
        with urlopen(f"{self.base_url}/api/recognition/catalog", timeout=2) as response:
            recognizers = json.load(response)["recognizers"]
        self.assertTrue(any(item["id"] == "local-auto" and not item["requires_explicit_consent"] for item in recognizers))
        self.assertTrue(any(item["id"] == "baidu-ocr" and item["requires_explicit_consent"] for item in recognizers))

        boundary = "----BuildCostIQRecognitionBoundary"
        parts = [
            ("project_id", "recognition-project", None),
            ("source_id", "article-source", None),
            ("file", "合同清单包含工程量和单价，等待结算核对。", "article.txt"),
        ]
        chunks: list[bytes] = []
        for name, value, filename in parts:
            chunks.append(f"--{boundary}\r\n".encode())
            if filename:
                chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
                chunks.append(b"Content-Type: text/plain; charset=utf-8\r\n\r\n")
            else:
                chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(value.encode("utf-8"))
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        upload_request = Request(
            f"{self.base_url}/api/source/upload",
            data=b"".join(chunks),
            headers=self.auth_headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urlopen(upload_request, timeout=2) as response:
            uploaded = json.load(response)
        recognition = uploaded["source"]["recognition"]
        self.assertEqual(recognition["mode"], "local")
        self.assertEqual(recognition["status"], "completed")
        self.assertIn("artifact", recognition)
        self.assertTrue(Path(uploaded["source"]["storage_path"]).is_file())
        self.assertTrue(Path(recognition["artifact"]["storage_path"]).is_file())
        with urlopen(self.auth_request("/api/workspace/recognition-project/bundle"), timeout=2) as response:
            with ZipFile(io.BytesIO(response.read())) as archive:
                self.assertIn("sources/article.txt", archive.namelist())
                self.assertIn("derived/article.md", archive.namelist())

        consent_request = Request(
            f"{self.base_url}/api/source/recognize",
            data=json.dumps({
                "project_id": "recognition-project",
                "source_id": "article-source",
                "connector_id": "baidu-ocr",
            }).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(consent_request, timeout=2) as response:
            gated = json.load(response)
        self.assertEqual(gated["recognition"]["status"], "consent_required")
        self.assertEqual(gated["workspace"]["sources"][0]["recognition"]["mode"], "local")


if __name__ == "__main__":
    unittest.main()
