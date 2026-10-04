from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from adapters.workspace import LocalProjectWorkspace
from domains.business_workflows import BusinessWorkflowError, BusinessWorkflowService, MODULES


class BusinessWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = LocalProjectWorkspace(Path(self.temp.name) / "projects")
        self.project_id = "single-project-test"
        self.workspace.create(self.project_id, "单项目合成验证")
        digest = hashlib.sha256(b"synthetic-evidence").hexdigest()
        self.workspace.add_source(self.project_id, {"source_id": "synthetic.pdf", "name": "合成证据.pdf", "content_hash": digest, "status": "active"})
        self.evidence = [f"sha256:{digest}"]
        self.service = BusinessWorkflowService(self.workspace)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def actor(user_id: str, role: str) -> dict[str, object]:
        return {"id": user_id, "username": user_id, "display_name": user_id, "role": role, "roles": [role]}

    def make_draft(self, module_id: str, evidence: list[str] | None = None) -> tuple[dict[str, object], str]:
        fields = {field["key"]: ("2026-10-04" if field["kind"] == "date" else "1" if field["kind"] == "decimal" else f"合成-{field['key']}") for field in MODULES[module_id]["fields"]}
        actor = self.actor(f"author-{module_id}", MODULES[module_id]["submit_roles"][0])
        result = self.service.apply(self.project_id, actor, {"action": "create", "module_id": module_id, "fields": fields, "evidence_refs": self.evidence if evidence is None else evidence, "idempotency_key": f"create-{module_id}"})
        run = next(item for item in result["runs"] if item["module_id"] == module_id)
        return actor, str(run["run_id"])

    def test_all_eight_professional_modules_have_live_contracts(self) -> None:
        result = self.service.snapshot(self.project_id)
        self.assertEqual(set(MODULES), {item["module_id"] for item in result["modules"]})
        self.assertEqual(8, len(result["modules"]))
        self.assertTrue(all(item["fields"] and item["steps"] for item in result["modules"]))
        self.assertTrue(result["ledger"]["valid"])

    def test_all_eight_professional_modules_complete_their_human_acceptance_path(self) -> None:
        for module_id, spec in MODULES.items():
            author, run_id = self.make_draft(module_id)
            self.service.apply(self.project_id, author, {"action": "submit", "module_id": module_id, "run_id": run_id, "idempotency_key": f"submit-all-{module_id}"})
            for index, step in enumerate(spec["steps"]):
                actor = self.actor(f"signer-{module_id}-{index}", step["roles"][0])
                result = self.service.apply(self.project_id, actor, {"action": "decide", "module_id": module_id, "run_id": run_id, "step": step["key"], "decision": "approve", "checklist": {key: True for key in step["checks"]}, "evidence_refs": self.evidence, "idempotency_key": f"approve-all-{module_id}-{index}"})
            completed = next(item for item in result["runs"] if item["run_id"] == run_id)
            self.assertEqual("accepted", completed["status"], module_id)

    def test_draft_requires_real_project_evidence_and_recovers_after_workspace_reopen(self) -> None:
        author, run_id = self.make_draft("01", evidence=[])
        state = next(item for item in self.service.snapshot(self.project_id)["runs"] if item["run_id"] == run_id)
        self.assertEqual("draft", state["status"])
        self.assertEqual("SCOPED", state["agent_ops_plan"]["state"])
        with self.assertRaises(BusinessWorkflowError):
            self.service.apply(self.project_id, author, {"action": "submit", "module_id": "01", "run_id": run_id, "idempotency_key": "submit-no-evidence"})
        reopened = BusinessWorkflowService(LocalProjectWorkspace(Path(self.temp.name) / "projects")).snapshot(self.project_id)
        recovered = next(item for item in reopened["runs"] if item["run_id"] == run_id)
        self.assertEqual("draft", recovered["status"])
        self.assertEqual("replayed", reopened["recovery"]["status"])

    def test_human_gate_requires_separation_checklist_and_evidence_then_accepts(self) -> None:
        author, run_id = self.make_draft("01")
        self.service.apply(self.project_id, author, {"action": "submit", "module_id": "01", "run_id": run_id, "idempotency_key": "submit-01"})
        state = next(item for item in self.service.snapshot(self.project_id)["runs"] if item["run_id"] == run_id)
        first = state["steps"][0]
        with self.assertRaises(BusinessWorkflowError):
            self.service.apply(self.project_id, author, {"action": "decide", "module_id": "01", "run_id": run_id, "step": first["key"], "decision": "approve", "checklist": {key: True for key in first["checks"]}, "evidence_refs": self.evidence, "idempotency_key": "self-approve"})
        with self.assertRaises(BusinessWorkflowError):
            self.service.apply(self.project_id, self.actor("reviewer", first["roles"][0]), {"action": "decide", "module_id": "01", "run_id": run_id, "step": first["key"], "decision": "approve", "checklist": {key: True for key in first["checks"]}, "evidence_refs": [], "idempotency_key": "no-evidence"})
        for index, step in enumerate(MODULES["01"]["steps"]):
            decision_actor = self.actor(f"reviewer-{index}", step["roles"][0])
            result = self.service.apply(self.project_id, decision_actor, {"action": "decide", "module_id": "01", "run_id": run_id, "step": step["key"], "decision": "approve", "checklist": {key: True for key in step["checks"]}, "evidence_refs": self.evidence, "idempotency_key": f"approve-01-{index}"})
        completed = next(item for item in result["runs"] if item["run_id"] == run_id)
        self.assertEqual("accepted", completed["status"])
        self.assertEqual("READY", completed["agent_ops_plan"]["state"])
        self.assertEqual(1, sum(event["event_type"] == "ACCEPTANCE_RECORDED" for event in completed["history"]))

    def test_return_reopens_for_correction_and_role_bound_handoff_is_single_use(self) -> None:
        author, run_id = self.make_draft("02")
        self.service.apply(self.project_id, author, {"action": "submit", "module_id": "02", "run_id": run_id, "idempotency_key": "submit-02"})
        first = MODULES["02"]["steps"][0]
        self.service.apply(self.project_id, self.actor("returner", first["roles"][0]), {"action": "decide", "module_id": "02", "run_id": run_id, "step": first["key"], "decision": "return", "note": "请补充答疑版本", "checklist": {key: False for key in first["checks"]}, "idempotency_key": "return-02"})
        state = next(item for item in self.service.snapshot(self.project_id)["runs"] if item["run_id"] == run_id)
        self.assertEqual("needs_correction", state["status"])
        self.service.apply(self.project_id, author, {"action": "update", "module_id": "02", "run_id": run_id, "fields": {"scope": "补正后招标范围"}, "evidence_refs": self.evidence, "idempotency_key": "update-02"})
        self.service.apply(self.project_id, author, {"action": "submit", "module_id": "02", "run_id": run_id, "idempotency_key": "resubmit-02"})
        for index, step in enumerate(MODULES["02"]["steps"]):
            result = self.service.apply(self.project_id, self.actor(f"approver-{index}", step["roles"][0]), {"action": "decide", "module_id": "02", "run_id": run_id, "step": step["key"], "decision": "approve", "checklist": {key: True for key in step["checks"]}, "evidence_refs": self.evidence, "idempotency_key": f"pass-02-{index}"})
        self.assertEqual("accepted", next(item for item in result["runs"] if item["run_id"] == run_id)["status"])
        result = self.service.apply(self.project_id, self.actor("handoff-manager", "cost_manager"), {"action": "handoff", "module_id": "02", "run_id": run_id, "target_module_id": "03", "idempotency_key": "handoff-02-03"})
        handoff = result["handoffs"][0]
        result = self.service.apply(self.project_id, self.actor("receiver", "cost_manager"), {"action": "consume_handoff", "module_id": "03", "handoff_id": handoff["handoff_id"], "idempotency_key": "consume-02-03"})
        self.assertEqual([], result["handoffs"])
        with self.assertRaises(BusinessWorkflowError):
            self.service.apply(self.project_id, self.actor("receiver2", "cost_manager"), {"action": "consume_handoff", "module_id": "03", "handoff_id": handoff["handoff_id"], "idempotency_key": "consume-again"})

    def test_content_addressed_workflow_record_tampering_fails_closed(self) -> None:
        self.make_draft("09")
        state = self.workspace.load(self.project_id)
        digest = next(iter(state["business_workflow_blobs"]))
        state["business_workflow_blobs"][digest]["fields"]["conclusion"] = "篡改"
        self.workspace.save(state)
        with self.assertRaises(BusinessWorkflowError):
            self.service.snapshot(self.project_id)


if __name__ == "__main__":
    unittest.main()
