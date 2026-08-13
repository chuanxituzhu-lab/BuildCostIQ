from __future__ import annotations

import io
import json
import threading
import unittest
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
        self.assertIn("项目经理工作台", body)
        self.assertIn("查看", body)

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
        manager = post_json("/api/auth/register", {"username": f"mgr-{suffix}", "password": "local-pass", "role": "project_manager"})
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
            headers={"Content-Type": "application/json"},
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
            headers={"Content-Type": "application/json"},
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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["capability_id"], "P05")
        self.assertEqual(result["summary"]["contract_item_count"], 1)
        self.assertEqual(result["items"][0]["status"], "contract")

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
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
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
            headers={"Content-Type": "application/json"},
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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(boq_request, timeout=2):
            pass
        with urlopen(f"{self.base_url}/api/workspace?project_id={project_id}", timeout=2) as response:
            workspace = json.load(response)
        self.assertEqual(workspace["project"]["name"], "工作区测试项目")
        self.assertEqual(workspace["boq"]["result"]["item_count"], 1)

        with urlopen(f"{self.base_url}/api/workspace/{project_id}/report", timeout=2) as response:
            report = response.read().decode("utf-8")
        self.assertIn("工作区测试项目", report)
        with urlopen(f"{self.base_url}/api/workspace/{project_id}/cost-plan.csv", timeout=2) as response:
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
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
        self.assertEqual(result["source"]["kind"], "Word 文档")
        self.assertEqual(result["workspace"]["sources"][0]["name"], "contract.docx")

    def test_connector_catalog_and_bidirectional_project_exchange(self):
        with urlopen(f"{self.base_url}/api/connectors", timeout=2) as response:
            catalog = json.load(response)["connectors"]
        self.assertEqual({item["id"] for item in catalog}, {"excel-csv", "word-report", "cad-quantity", "budget-software", "project-bundle"})

        project_id = "exchange-test"
        project_request = Request(
            f"{self.base_url}/api/project",
            data=json.dumps({"project_id": project_id, "name": "交换测试项目"}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(boq_request, timeout=2):
            pass

        for suffix in ("boq.xlsx", "cost-plan.xlsx"):
            with urlopen(f"{self.base_url}/api/workspace/{project_id}/{suffix}", timeout=2) as response:
                self.assertEqual(response.read(2), b"PK")

        with urlopen(f"{self.base_url}/api/workspace/{project_id}/bundle", timeout=2) as response:
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
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
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
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlopen(upload_request, timeout=2) as response:
            uploaded = json.load(response)
        recognition = uploaded["source"]["recognition"]
        self.assertEqual(recognition["mode"], "local")
        self.assertEqual(recognition["status"], "completed")
        self.assertIn("artifact", recognition)
        with urlopen(f"{self.base_url}/api/workspace/recognition-project/bundle", timeout=2) as response:
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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(consent_request, timeout=2) as response:
            gated = json.load(response)
        self.assertEqual(gated["recognition"]["status"], "consent_required")
        self.assertEqual(gated["workspace"]["sources"][0]["recognition"]["mode"], "local")


if __name__ == "__main__":
    unittest.main()
