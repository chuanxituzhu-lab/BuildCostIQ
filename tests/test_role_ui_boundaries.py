from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from gui.server import _ROLE_WORKSPACE_VIEWS, create_server


ROOT = Path(__file__).resolve().parents[1]


class RoleUiBoundaryTests(unittest.TestCase):
    def test_frontend_role_catalog_matches_server_and_has_no_stale_baseline(self):
        app_text = (ROOT / "gui" / "static" / "app.js").read_text(encoding="utf-8")
        match = re.search(r"const ROLE_VIEW_ACCESS = \{(?P<body>.*?)\n\};", app_text, re.DOTALL)
        self.assertIsNotNone(match, "前端岗位菜单目录缺失")
        frontend: dict[str, set[str]] = {}
        for entry in re.finditer(r"^  ([a-z_]+): \[(.*?)\],$", match.group("body"), re.MULTILINE):
            frontend[entry.group(1)] = set(ast.literal_eval(f"[{entry.group(2)}]"))
        self.assertEqual(frontend, _ROLE_WORKSPACE_VIEWS)
        for role in ("production_manager", "surveyor", "document_controller", "procurement_officer", "warehouse_officer"):
            self.assertNotIn("baseline", frontend[role])
        for role in ("technical_lead", "production_manager", "site_engineer", "surveyor", "quality_officer", "lab_testing_officer", "safety_officer", "procurement_officer", "warehouse_officer", "administrative_officer"):
            self.assertNotIn("search", frontend[role])
        self.assertIn("ROLE-OWNED WORK PRODUCTS", app_text)
        self.assertIn("data-role-product-form", app_text)
        self.assertIn("saveRoleWorkProduct", app_text)

    def test_warehouse_and_field_roles_are_denied_unrelated_search_and_baseline(self):
        server = create_server("127.0.0.1", 0)
        server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"

        def post(path: str, payload: dict, token: str | None = None) -> dict:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = Request(
                f"{base_url}{path}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                return json.load(response)

        try:
            manager = post("/api/auth/register", {"username": f"role-boundary-manager-{uuid4().hex[:8]}", "password": "local-pass", "role": "cost_manager"})
            manager_token = manager["token"]
            project_id = f"role-boundary-{uuid4().hex[:8]}"
            post("/api/project", {"project_id": project_id, "name": "岗位边界复核项目"}, manager_token)
            warehouse = post("/api/auth/register", {"username": f"warehouse-{uuid4().hex[:8]}", "password": "local-pass", "role": "warehouse_officer"}, manager_token)
            warehouse_token = warehouse["token"]
            with urlopen(Request(f"{base_url}/api/workspace?project_id={project_id}", headers={"Authorization": f"Bearer {warehouse_token}"}), timeout=2) as response:
                workspace = json.load(response)
            self.assertEqual(set(workspace["visible_views"]), _ROLE_WORKSPACE_VIEWS["warehouse_officer"])
            self.assertNotIn("baseline", workspace)
            self.assertNotIn("search", workspace["visible_views"])

            with self.assertRaises(HTTPError) as denied_search:
                post("/api/search", {"project_id": project_id, "query": "材料"}, warehouse_token)
            self.assertEqual(denied_search.exception.code, 403)

            with self.assertRaises(HTTPError) as denied_baseline:
                post(
                    "/api/baseline",
                    {"project_id": project_id, "source_id": "warehouse-baseline", "entries": [{"name": "管材", "quantity": 1, "unit_price": 1}]},
                    warehouse_token,
                )
            self.assertEqual(denied_baseline.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
