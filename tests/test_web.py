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
        self.assertIn('id="basisInput"', body)
        self.assertIn('id="basisInput" class="visually-hidden" type="file" multiple', body)
        self.assertIn("multiple", body)
        self.assertIn(".pdf", body)
        self.assertIn('id="loginForm"', body)
        self.assertIn('id="deploymentStatus"', body)
        self.assertIn('id="personnelTab"', body)
        self.assertIn("项目经理工作台", body)
        self.assertIn("施工员/测量员", body)
        self.assertIn("经营看板", body)

        with urlopen(f"{self.base_url}/api/health", timeout=2) as response:
            health = json.load(response)
        self.assertEqual(health["review_capability"], "P08")
        self.assertEqual(health["runtime"]["capabilities"], [f"P{i:02d}" for i in range(1, 10)])
        self.assertIn("deployment", health)
        self.assertIn("project_write_lock", health["deployment"]["consistency"])

        with urlopen(f"{self.base_url}/api/deployment", timeout=2) as response:
            deployment = json.load(response)
        self.assertEqual(deployment["deployment"]["version"], "1.0")
        self.assertFalse(deployment["deployment"]["consistency"]["direct_shared_folder_writes"])

        with urlopen(f"{self.base_url}/api/architecture", timeout=2) as response:
            architecture = json.load(response)
        self.assertEqual(architecture["registered"], [f"P{i:02d}" for i in range(1, 10)])
        self.assertEqual(architecture["capabilities"][-1]["id"], "P09")
        self.assertEqual(architecture["capabilities"][-1]["status"], "implemented")
        self.assertTrue(any(layer["id"] == "gateway" for layer in architecture["layers"]))
        with urlopen(f"{self.base_url}/api/line-contracts", timeout=2) as response:
            contracts = json.load(response)
        self.assertEqual(contracts["role_workbench"]["version"], "1.0")
        self.assertEqual(contracts["role_workbench"]["roles"]["warehouse_officer"]["product_type"], "inventory_movement")
        self.assertEqual(contracts["role_workbench"]["roles"]["surveyor"]["product_type"], "survey_result")

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
            'Content-Disposition: form-data; name="file"; filename="资料台账.txt"\r\n'
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

    def test_role_workbench_projection_and_capability_boundary(self):
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
            result = post_json("/api/auth/register", {"username": f"{role}-{suffix}", "password": "local-pass", "role": role}, self.manager_token)
            return result["token"]

        project_id = f"role-workbench-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "岗位工作台边界测试项目"}, self.manager_token)
        site_token = register("site_engineer")
        tech_token = register("technical_lead")
        post_json("/api/drawings", {"project_id": project_id, "source_id": "role-drawing", "drawings": [{"drawing_no": "S-01", "name": "道路平面"}]}, self.manager_token)

        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}", site_token), timeout=2) as response:
            site_workspace = json.load(response)
        self.assertIn("drawings", site_workspace["visible_views"])
        self.assertNotIn("contract", site_workspace["visible_views"])
        self.assertNotIn("baseline", site_workspace["visible_views"])
        self.assertNotIn("contract", site_workspace)
        self.assertNotIn("baseline", site_workspace)

        with urlopen(self.auth_request(f"/api/workspace?project_id={project_id}", tech_token), timeout=2) as response:
            tech_workspace = json.load(response)
        self.assertIn("changes", tech_workspace["visible_views"])
        self.assertNotIn("boq", tech_workspace["visible_views"])
        self.assertNotIn("boq", tech_workspace)

        with self.assertRaises(HTTPError) as denied_boq:
            post_json("/api/boq", {"project_id": project_id, "source_id": "role-boq", "rows": [["项目编码", "项目名称", "计量单位", "工程量"], ["0101", "土方", "m3", 1]]}, site_token)
        self.assertEqual(denied_boq.exception.code, 403)
        with self.assertRaises(HTTPError) as denied_dashboard:
            urlopen(self.auth_request(f"/api/dashboard?project_id={project_id}", tech_token), timeout=2)
        self.assertEqual(denied_dashboard.exception.code, 403)

        # P04 is a cost opening baseline: field and production roles may use
        # derived references, but cannot enter or modify the zero ledger.
        production_token = register("production_manager")
        with self.assertRaises(HTTPError) as denied_baseline:
            post_json(
                "/api/baseline",
                {"project_id": project_id, "source_id": "role-baseline", "entries": [{"name": "土方", "quantity": 1, "unit_price": 1}]},
                production_token,
            )
        self.assertEqual(denied_baseline.exception.code, 403)

        with self.assertRaises(HTTPError) as denied_p09:
            urlopen(self.auth_request(f"/api/p09?project_id={project_id}", tech_token), timeout=2)
        self.assertEqual(denied_p09.exception.code, 403)

        with urlopen(self.auth_request(f"/api/dashboard?project_id={project_id}", production_token), timeout=2) as response:
            production_dashboard = json.load(response)
        self.assertEqual(production_dashboard["outcome_management"]["status"], "restricted")
        self.assertEqual(production_dashboard["capabilities"]["P09"]["status"], "restricted")

    def test_personnel_management_is_project_manager_controlled_with_admin_delegation(self):
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

        project_manager = post_json("/api/auth/register", {"username": f"personnel-project-manager-{suffix}", "password": "local-pass", "role": "project_manager"}, self.manager_token)
        project_manager_token = project_manager["token"]
        admin = post_json("/api/auth/register", {"username": f"personnel-admin-{suffix}", "password": "local-pass", "role": "administrative_officer"}, project_manager_token)
        admin_token = admin["token"]
        estimator_token = register("cost_estimator", self.manager_token)

        with self.assertRaises(HTTPError) as denied_cost_manager:
            urlopen(self.auth_request("/api/personnel", self.manager_token), timeout=2)
        self.assertEqual(denied_cost_manager.exception.code, 403)

        for token in (project_manager_token,):
            with urlopen(self.auth_request("/api/personnel", token), timeout=2) as response:
                snapshot = json.load(response)
            self.assertIn("users", snapshot)
            self.assertIn("audit_log", snapshot)
            self.assertIn("roles", snapshot)
            self.assertEqual(snapshot["policy"]["delegated_manager_role"], "administrative_officer")
            self.assertTrue(all("password" not in user for user in snapshot["users"]))

        project_manager_created = post_json(
            "/api/personnel",
            {"username": f"created-by-project-manager-{suffix}", "password": "local-pass", "role": "cost_estimator"},
            project_manager_token,
        )
        self.assertTrue(any(user["username"] == f"created-by-project-manager-{suffix}" for user in project_manager_created["users"]))
        self.assertIn("personnel.created", [event["action"] for event in project_manager_created["audit_log"]])

        managed_personnel = post_json(
            "/api/personnel",
            {"name": f"managed-warehouse-{suffix}", "role": "warehouse_officer"},
            project_manager_token,
        )
        credentials = managed_personnel["temporary_credentials"]
        self.assertEqual(credentials["username"], f"managed-warehouse-{suffix}")
        self.assertEqual(credentials["role"], "warehouse_officer")
        managed_login = post_json(
            "/api/auth/login",
            {"username": credentials["username"], "password": credentials["password"]},
            project_manager_token,
        )
        self.assertEqual(managed_login["user"]["role"], "warehouse_officer")
        with urlopen(self.auth_request("/api/personnel", project_manager_token), timeout=2) as response:
            refreshed_personnel = json.load(response)
        self.assertNotIn("temporary_credentials", refreshed_personnel)

        field_user = post_json(
            "/api/personnel",
            {"username": f"field-a-{suffix}", "password": "local-pass", "role": "surveyor"},
            project_manager_token,
        )
        field_record = next(item for item in field_user["users"] if item["username"] == f"field-a-{suffix}")
        field_session = post_json("/api/auth/login", {"username": f"field-a-{suffix}", "password": "local-pass"}, project_manager_token)
        handed_over = post_json(
            "/api/personnel/rename",
            {"user_id": field_record["id"], "new_username": f"field-b-{suffix}"},
            project_manager_token,
        )
        renamed_record = next(item for item in handed_over["users"] if item["id"] == field_record["id"])
        self.assertEqual(renamed_record["username"], f"field-b-{suffix}")
        self.assertEqual(renamed_record["name_history"][0]["username"], f"field-a-{suffix}")
        with urlopen(self.auth_request("/api/auth/me", field_session["token"]), timeout=2) as response:
            self.assertEqual(json.load(response)["user"]["username"], f"field-b-{suffix}")
        merged = post_json(
            "/api/personnel/roles",
            {"user_id": field_record["id"], "roles": ["surveyor", "site_engineer"]},
            project_manager_token,
        )
        merged_record = next(item for item in merged["users"] if item["id"] == field_record["id"])
        self.assertEqual(merged_record["role_assignment"], "merged")
        login = post_json("/api/auth/login", {"username": f"field-b-{suffix}", "password": "local-pass"}, project_manager_token)
        self.assertEqual(login["user"]["id"], field_record["id"])
        with self.assertRaises(HTTPError):
            post_json("/api/auth/login", {"username": f"field-a-{suffix}", "password": "local-pass"}, project_manager_token)

        with self.assertRaises(HTTPError) as denied_admin_before_grant:
            urlopen(self.auth_request("/api/personnel", admin_token), timeout=2)
        self.assertEqual(denied_admin_before_grant.exception.code, 403)

        authorized = post_json("/api/personnel/authorize", {"user_id": admin["user"]["id"], "authorized": True}, project_manager_token)
        self.assertTrue(next(item for item in authorized["users"] if item["id"] == admin["user"]["id"])["personnel_admin_authorized"])
        with urlopen(self.auth_request("/api/personnel", admin_token), timeout=2) as response:
            delegated_snapshot = json.load(response)
        self.assertTrue(any(item["username"] == f"personnel-admin-{suffix}" for item in delegated_snapshot["users"]))
        delegated_created = post_json(
            "/api/personnel",
            {"name": f"created-by-admin-{suffix}", "role": "quality_officer"},
            admin_token,
        )
        delegated_credentials = delegated_created["temporary_credentials"]
        delegated_login = post_json(
            "/api/auth/login",
            {"username": delegated_credentials["username"], "password": delegated_credentials["password"]},
            admin_token,
        )
        self.assertEqual(delegated_login["user"]["role"], "quality_officer")

        deleted = post_json("/api/personnel/delete", {"user_id": admin["user"]["id"]}, project_manager_token)
        self.assertFalse(any(item["id"] == admin["user"]["id"] for item in deleted["users"]))
        self.assertIn("personnel.deleted", [event["action"] for event in deleted["audit_log"]])

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

    def test_personnel_rosters_are_isolated_by_project(self):
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

        project_manager = post_json(
            "/api/auth/register",
            {"username": f"project-manager-isolated-{suffix}", "password": "local-pass", "role": "project_manager"},
            self.manager_token,
        )
        project_manager_token = project_manager["token"]
        project_a = f"personnel-project-a-{suffix}"
        project_b = f"personnel-project-b-{suffix}"
        post_json("/api/project", {"project_id": project_a, "name": "项目 A"}, self.manager_token)
        post_json("/api/project", {"project_id": project_b, "name": "项目 B"}, self.manager_token)

        def get_snapshot(project_id):
            with urlopen(self.auth_request(f"/api/personnel?project_id={project_id}", project_manager_token), timeout=2) as response:
                return json.load(response)

        snapshot_a = get_snapshot(project_a)
        snapshot_b = get_snapshot(project_b)
        self.assertEqual(snapshot_a["project_id"], project_a)
        self.assertEqual(snapshot_b["project_id"], project_b)
        base_count = len(snapshot_a["users"])
        self.assertGreater(base_count, 0)
        self.assertEqual(len(snapshot_b["users"]), base_count)

        created = post_json(
            "/api/personnel",
            {"project_id": project_a, "name": f"项目A仓管-{suffix}", "role": "warehouse_officer"},
            project_manager_token,
        )
        # The baseline roster is deployment-local and may contain a different
        # number of seeded users in an isolated test run.  Project personnel
        # management must add exactly one member to this project only.
        self.assertEqual(len(created["users"]), base_count + 1)
        self.assertTrue(any(item["username"] == f"项目A仓管-{suffix}" for item in created["users"]))
        self.assertEqual(len(get_snapshot(project_b)["users"]), base_count)

        created_user = next(item for item in created["users"] if item["username"] == f"项目A仓管-{suffix}")
        removed = post_json(
            "/api/personnel/delete",
            {"project_id": project_a, "user_id": created_user["id"]},
            project_manager_token,
        )
        self.assertEqual(len(removed["users"]), base_count)
        self.assertEqual(len(get_snapshot(project_b)["users"]), base_count)

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
        self.assertEqual(result["source"]["archive_area"], "清单与计价资料")
        self.assertIn("archive_path", result["source"])
        self.assertIn("storage_path", result["source"])

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
            ("archive_area", "项目资料库/合同与招采依据", None),
            ("archive_category", "招标阶段", None),
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
        self.assertEqual(result["source"]["archive_path"], "项目资料库/合同与招采依据/招标阶段/contract.docx")
        self.assertEqual(result["workspace"]["sources"][0]["name"], "contract.docx")
        archive_storage_path = Path(result["source"]["archive_storage_path"])
        self.assertTrue(archive_storage_path.is_file())
        self.assertEqual(archive_storage_path.read_bytes(), b"fake-word-content")
        self.assertIn("招标阶段", archive_storage_path.parts)
        self.assertTrue(Path(result["source"]["storage_path"]).is_file())

    def test_source_upload_can_defer_local_recognition_after_fast_save(self):
        project_id = f"deferred-source-{uuid4().hex[:10]}"
        boundary = "----BuildCostIQDeferredRecognition"
        chunks = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n{project_id}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"source_id\"\r\n\r\ndeferred-source\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"recognize\"\r\n\r\nfalse\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"deferred.txt\"\r\nContent-Type: text/plain\r\n\r\n本地先保存，识别稍后进行。\r\n".encode("utf-8"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        request = Request(
            f"{self.base_url}/api/source/upload",
            data=b"".join(chunks),
            headers=self.auth_headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            saved = json.load(response)
        self.assertNotEqual((saved["source"].get("recognition") or {}).get("status"), "completed")
        self.assertTrue(Path(saved["source"]["storage_path"]).is_file())

        recognized = Request(
            f"{self.base_url}/api/source/recognize",
            data=json.dumps({"project_id": project_id, "source_id": "deferred-source", "connector_id": "local-auto"}).encode("utf-8"),
            headers=self.auth_headers("application/json"),
            method="POST",
        )
        with urlopen(recognized, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["recognition"]["status"], "completed")

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

    def test_local_search_returns_traceable_evidence_and_honest_no_hit(self):
        boundary = "----BuildCostIQSearchBoundary"
        chunks: list[bytes] = []
        for name, value, filename in [
            ("project_id", "search-project", None),
            ("source_id", "search-source", None),
            ("file", "合同清单包含工程量和单价，结算依据为本地合同文件。", "搜索资料.txt"),
        ]:
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
        with urlopen(upload_request, timeout=2):
            pass

        def search(query: str, mode: str = "search"):
            request = Request(
                f"{self.base_url}/api/search",
                data=json.dumps({"project_id": "search-project", "query": query, "mode": mode, "scope": "project"}, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json"),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        found = search("工程量和单价")
        self.assertGreaterEqual(found["total"], 1)
        self.assertTrue(any(item["match_status"] == "supported" for item in found["results"]))
        serialized = json.dumps(found, ensure_ascii=False)
        self.assertNotIn("content_hash", serialized)
        self.assertNotIn("document_id", serialized)
        self.assertIn("archive_path", serialized)
        self.assertTrue(all(item["provenance"]["external_sent"] is False for item in found["results"]))

        answer = search("火星档案不存在", "ask")
        self.assertEqual(answer["answer_mode"], "local_evidence_summary")
        self.assertIn("不能对这个问题给出确定结论", answer["answer"])
        self.assertEqual(answer["external_ai"]["sent"], False)

        pm_request = Request(
            f"{self.base_url}/api/auth/register",
            data=json.dumps({"username": f"search-pm-{uuid4().hex[:8]}", "password": "local-pass", "role": "project_manager"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(pm_request, timeout=2) as response:
            pm_token = json.load(response)["token"]
        pm_search = Request(
            f"{self.base_url}/api/search",
            data=json.dumps({"project_id": "search-project", "query": "工程量", "scope": "all"}, ensure_ascii=False).encode("utf-8"),
            headers=self.auth_headers("application/json", pm_token),
            method="POST",
        )
        with urlopen(pm_search, timeout=2) as response:
            pm_result = json.load(response)
        self.assertTrue(pm_result["results"])
        self.assertTrue(all(item["openable"] is False and item["storage_path"] == "" for item in pm_result["results"]))
        self.assertFalse(any(item["result_id"].startswith("external-basis:") for item in pm_result["results"]))

    def test_event_kernel_distills_fuses_and_creates_permanent_event(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token=None):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json", token or self.manager_token),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        project_id = f"event-kernel-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "工程事件测试项目"})
        distillation = post_json(
            "/api/event-kernel/distill",
            {"project_id": project_id, "text": "设计变更发生在 K12+300，预计增加 120 m3，影响成本和工期。", "text_source_ref": "纪要-01"},
        )
        self.assertGreater(distillation["distillation"]["summary"]["local_fact_count"], 0)
        self.assertGreater(distillation["distillation"]["summary"]["text_fact_count"], 0)
        self.assertFalse(distillation["distillation"]["external_sent"])
        event_result = post_json(
            "/api/event-kernel/events",
            {
                "project_id": project_id,
                "title": "现场发现设计变化",
                "summary": "发现设计变化，需要技术判断",
                "source_type": "DESIGN_CHANGE",
                "event_type": "DESIGN_CHANGE",
                "severity": "HIGH",
                "discovered_by": "测试人员",
                "location": {"zone": "K12+300"},
                "source_refs": ["纪要-01"],
                "dimensions": {"cost": True, "schedule": True},
                "baseline_impact": {"quantity": {"affected": True}},
                "technical_track": {"needed": True, "assessment": "需要技术判断"},
                "commercial_track": {"evaluations": [{"option_id": "OPT-1", "expected_profit": 10000}]},
            },
        )
        event = event_result["event"]
        self.assertRegex(event["event_id"], r"^EV-\d{4}-\d{4}$")
        self.assertEqual(event["state_vector"]["event"], "DISCOVERED")
        progressed = post_json("/api/event-kernel/transition", {"project_id": project_id, "event_id": event["event_id"], "target_status": "ASSESSED"})
        self.assertEqual(progressed["event"]["state_vector"]["event"], "ASSESSED")
        with urlopen(self.auth_request(f"/api/event-kernel?project_id={project_id}"), timeout=2) as response:
            kernel = json.load(response)
        self.assertEqual(len(kernel["events"]), 1)
        self.assertEqual(kernel["privacy"]["external_sent"], False)

    def test_event_kernel_redacts_cost_detail_for_estimator_and_pm(self):
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

        estimator = post_json("/api/auth/register", {"username": f"event-est-{suffix}", "password": "local-pass", "role": "cost_estimator"}, self.manager_token)
        pm = post_json("/api/auth/register", {"username": f"event-pm-{suffix}", "password": "local-pass", "role": "project_manager"}, self.manager_token)
        project_id = f"event-roles-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "事件角色项目"}, estimator["token"])
        created = post_json(
            "/api/event-kernel/events",
            {"project_id": project_id, "title": "成本事件", "summary": "成本测算", "commercial_track": {"expected_profit": 987654, "evaluations": [{"incremental_cost": 123456}]}, "settlement": {"final_certified": 999999}, "source_refs": ["S-1"]},
            estimator["token"],
        )
        serialized = json.dumps(created, ensure_ascii=False)
        self.assertNotIn("987654", serialized)
        with urlopen(self.auth_request(f"/api/event-kernel?project_id={project_id}", estimator["token"]), timeout=2) as response:
            estimator_kernel = json.load(response)
        self.assertIsNone(estimator_kernel["events"][0]["commercial_track"]["expected_profit"])
        with urlopen(self.auth_request(f"/api/event-kernel?project_id={project_id}", pm["token"]), timeout=2) as response:
            pm_kernel = json.load(response)
        self.assertNotIn("commercial_track", pm_kernel["events"][0])

    def test_outcome_endpoint_and_dashboard_funnel_keep_one_source_of_truth(self):
        suffix = uuid4().hex[:10]

        def post_json(path, payload, token=None):
            request = Request(
                f"{self.base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self.auth_headers("application/json", token or self.manager_token),
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        project_id = f"outcome-web-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "成果链测试项目"})
        created = post_json(
            "/api/event-kernel/events",
            {
                "project_id": project_id,
                "title": "地下管线冲突",
                "summary": "形成可计量工程成果",
                "discovered_by": "现场员",
                "location": {"zone": "K12"},
                "source_refs": ["S-01"],
                "dimensions": {"cost": True, "revenue": True},
            },
        )
        event_id = created["event"]["event_id"]
        updated = post_json(
            "/api/event-kernel/outcome",
            {"project_id": project_id, "event_id": event_id, "operation": "snapshot", "changes": {"types": ["PHYSICAL", "COMMERCIAL"], "values": {"physical": 1000, "evidence_ready": 900, "submitted": 850, "confirmed": 800, "settled": 700, "paid": 500}}},
        )
        self.assertEqual(updated["outcome"]["value_leak_count"], 5)
        self.assertEqual(len(updated["event"]["outcome_track"]["revisions"]), 1)
        dashboard_request = self.auth_request(f"/api/dashboard?project_id={project_id}")
        with urlopen(dashboard_request, timeout=2) as response:
            dashboard = json.load(response)
        outcome = dashboard["outcome_management"]
        self.assertEqual(outcome["value_leak_count"], 5)
        self.assertEqual(outcome["funnel"][0]["amount"], 1000.0)
        self.assertTrue(outcome["rules"]["event_closed_not_outcome_closed"])

        pm = post_json("/api/auth/register", {"username": f"outcome-pm-{suffix}", "password": "local-pass", "role": "project_manager"}, self.manager_token)
        with urlopen(self.auth_request(f"/api/dashboard?project_id={project_id}", pm["token"]), timeout=2) as response:
            pm_dashboard = json.load(response)
        self.assertIsNone(pm_dashboard["outcome_management"]["funnel"][0]["amount"])
        self.assertEqual(pm_dashboard["outcome_management"]["value_leak_count"], 5)

        with urlopen(self.auth_request(f"/api/p09?project_id={project_id}"), timeout=2) as response:
            p09 = json.load(response)
        self.assertEqual(p09["capability_id"], "P09")
        self.assertEqual(p09["summary"]["event_count"], 1)
        self.assertTrue(p09["rules"]["derived_values_only"])

    def test_role_work_products_are_distinct_and_handoff_scoped(self):
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

        warehouse = post_json(
            "/api/auth/register",
            {"username": f"warehouse-product-{suffix}", "password": "local-pass", "role": "warehouse_officer"},
            self.manager_token,
        )
        production = post_json(
            "/api/auth/register",
            {"username": f"production-product-{suffix}", "password": "local-pass", "role": "production_manager"},
            self.manager_token,
        )
        site = post_json(
            "/api/auth/register",
            {"username": f"site-product-{suffix}", "password": "local-pass", "role": "site_engineer"},
            self.manager_token,
        )
        project_id = f"role-products-{suffix}"
        post_json("/api/project", {"project_id": project_id, "name": "岗位成果契约项目"}, self.manager_token)
        created = post_json(
            "/api/role-work-products",
            {
                "project_id": project_id,
                "role": "warehouse_officer",
                "fields": {
                    "movement_type": "ISSUE",
                    "material_batch": "STEEL-01",
                    "document_ref": "领料-01",
                    "quantity": 12,
                    "unit": "t",
                    "location": "K12+300",
                    "recipient": "一工班",
                    "inventory_after": 88,
                    "check_status": "CHECKED",
                },
                "handoff_to": "production_manager",
                "event_id": "EV-2026-0001",
                "evidence_refs": "IMG-01",
            },
            warehouse["token"],
        )
        self.assertEqual(created["record"]["product_type"], "inventory_movement")
        self.assertEqual(created["record"]["collaboration"]["handoff_to"], ["production_manager"])
        with urlopen(self.auth_request(f"/api/role-work-products?project_id={project_id}", warehouse["token"]), timeout=2) as response:
            warehouse_view = json.load(response)
        self.assertEqual(warehouse_view["contracts"]["warehouse_officer"]["product_type"], "inventory_movement")
        self.assertEqual(len(warehouse_view["records"]), 1)
        with urlopen(self.auth_request(f"/api/role-work-products?project_id={project_id}", production["token"]), timeout=2) as response:
            production_view = json.load(response)
        self.assertEqual(production_view["incoming_count"], 1)
        self.assertEqual(production_view["records"][0]["role"], "warehouse_officer")
        with self.assertRaises(HTTPError) as denied:
            post_json(
                "/api/role-work-products",
                {"project_id": project_id, "role": "warehouse_officer", "fields": {}},
                site["token"],
            )
        self.assertEqual(denied.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
