from __future__ import annotations

import unittest

from core import (
    EventKernelError,
    build_state_vector,
    distill_local_data,
    distill_text,
    evaluate_event_rules,
    fuse_distillations,
    new_event,
    run_cross_check,
    transition_event,
)


class EventKernelTests(unittest.TestCase):
    def test_local_then_text_distillation_keeps_provenance_and_conflict(self):
        local = distill_local_data(
            {
                "project": {"id": "p-1", "name": "测试项目"},
                "sources": [{"source_id": "S-01", "name": "现场记录.pdf"}],
                "changes": {"result": {"changes": [{"change_id": "CH-01", "title": "设计变化", "reason": "增加工程量", "status": "pending", "amount": 100, "source_id": "S-01"}] }},
            }
        )
        local["facts"].append({"fact_id": "LOCAL-999", "kind": "classification.event_type", "value": "SITE_CONDITION", "source_refs": ["S-01"], "confidence": 0.99, "origin": "LOCAL_PROJECT"})
        text = distill_text("设计变更发生在 K12+300，预计增加 120 m3，影响成本和工期。", "TEXT-01", "p-1")
        fused = fuse_distillations(local, text, "p-1")
        self.assertEqual(local["origin"], "LOCAL_PROJECT")
        self.assertEqual(text["origin"], "DISTILLED_TEXT")
        self.assertEqual(fused["origin"], "FUSED_LOCAL_TEXT")
        self.assertTrue(all(item["source_refs"] for item in fused["fused_facts"]))
        self.assertEqual(fused["claims"][0]["status"], "UNVERIFIED")

    def test_event_guards_require_real_business_facts(self):
        event = new_event("p-1", event_id="EV-2026-0001", title="现场条件", summary="发现现场条件变化", discovered_by="现场员", location={"zone": "K12"}, source_refs=["S-01"], dimensions={"cost": True})
        event["baseline_impact"]["quantity"]["affected"] = True
        event["technical_track"]["needed"] = True
        assessed = transition_event(event, "ASSESSED")
        planned = transition_event(assessed, "PLANNING")
        with self.assertRaises(EventKernelError):
            transition_event(planned, "COMMERCIAL_REVIEW")
        planned["technical_track"]["options"] = [{"option_id": "OPT-1", "feasible": True, "safety_pass": True, "quality_pass": True, "compliance_pass": True}]
        planned["technical_track"]["status"] = "FEASIBLE"
        commercial_review = transition_event(planned, "COMMERCIAL_REVIEW")
        self.assertEqual(commercial_review["status"], "COMMERCIAL_REVIEW")
        self.assertEqual(len(commercial_review["governance"]["status_history"]), 4)

    def test_state_vector_and_local_rules_surface_management_risk(self):
        event = new_event("p-1", event_id="EV-2026-0002", title="已实施事项", summary="施工完成", discovered_by="现场员", location={"zone": "A"}, source_refs=["S-02"], dimensions={"cost": True})
        event["production_track"]["progress"] = 80
        event["commercial_track"]["claim_status"] = "NOT_CREATED"
        event["evidence"]["three_evidence"]["completeness"] = 20
        vector = build_state_vector(event)
        alerts = evaluate_event_rules(event)
        self.assertEqual(vector["production"], 80.0)
        self.assertTrue(any(item["rule_id"] == "EVENT-EVIDENCE-01" for item in alerts))

    def test_cross_check_detects_location_and_quantity_conflict(self):
        event = new_event("p-1", event_id="EV-2026-0003", title="数量变化", summary="数量不一致", discovered_by="现场员", location={"zone": "A"}, source_refs=["S-03"], dimensions={"quantity": True})
        event["production_track"]["actual"]["location"] = {"zone": "B"}
        event["production_track"]["actual"]["quantity"] = 120
        event["baseline_impact"]["quantity"].update({"original_quantity": 100, "affected": True})
        result = run_cross_check(event)
        self.assertEqual(result["status"], "CONFLICT")
        self.assertTrue({"LOCATION", "QUANTITY"}.issubset({item["check_id"] for item in result["checks"] if item["status"] == "CONFLICT"}))


if __name__ == "__main__":
    unittest.main()
