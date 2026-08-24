from __future__ import annotations

import unittest

from adapters.event_intake import build_event_requirements, derive_event_intake, match_event_candidates


class EventIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = {
            "event_id": "EV-2026-0001",
            "status": "DISCOVERED",
            "identity": {"title": "地下管线冲突", "summary": "现场发现既有管线与施工范围冲突"},
            "classification": {"event_type": "SITE_CONDITION", "tags": ["管线"]},
            "origin": {"discovered_at": "2026-08-24T00:00:00+00:00", "location": {"zone": "K12+300"}},
        }

    def test_daily_log_and_photo_record_only_becomes_explainable_candidate(self):
        product = {
            "product_id": "WP-SITE-1",
            "role": "site_engineer",
            "product_type": "site_fact",
            "fields": {
                "daily_log_ref": "LOG-001",
                "log_date": "2026-08-24",
                "location": "K12+300",
                "work_activity": "沟槽开挖",
                "condition": "发现地下管线冲突，现场照片已记录",
                "photo_refs": "PHOTO-01,PHOTO-02",
            },
            "links": {"source_refs": ["LOG-001", "PHOTO-01"]},
        }
        candidates = match_event_candidates(product, [self.event])
        self.assertEqual(candidates[0]["event_id"], "EV-2026-0001")
        self.assertIn("管线", candidates[0]["matched_keywords"])
        packet = derive_event_intake({"events": [self.event], "role_work_products": [product]}, ["site_engineer"])
        self.assertEqual(packet[0]["status"], "SUGGESTED")
        self.assertTrue(packet[0]["requires_cost_manager"])
        self.assertEqual(packet[0]["event_id"], "")

    def test_event_requirements_are_fixed_and_have_due_time(self):
        packet = build_event_requirements({"events": [self.event], "role_work_products": []}, ["site_engineer", "technical_lead"])
        self.assertEqual({item["role"] for item in packet}, {"site_engineer", "technical_lead"})
        site = next(item for item in packet if item["role"] == "site_engineer")
        self.assertEqual(site["status"], "OPEN")
        self.assertTrue(site["fixed_assignment"])
        self.assertEqual(site["due_at"], "2026-08-25T00:00:00+00:00")
        self.assertIn("施工日志", site["deliverables"])

    def test_already_confirmed_link_is_not_requeued(self):
        product = {"product_id": "WP-SITE-2", "role": "site_engineer", "links": {"event_id": "EV-2026-0001"}}
        packet = derive_event_intake({"events": [self.event], "role_work_products": [product]}, ["site_engineer"])
        self.assertEqual(packet[0]["status"], "LINKED")
        self.assertFalse(packet[0]["requires_cost_manager"])

    def test_returned_evidence_keeps_feedback_on_fixed_requirement(self):
        product = {
            "product_id": "WP-SITE-RETURNED",
            "role": "site_engineer",
            "links": {"event_id": "EV-2026-0001"},
            "event_review_state": "RETURNED",
            "event_feedback": {"reason": "缺少隐蔽验收照片", "required_items": ["隐蔽验收照片"]},
        }
        state = {"events": [self.event], "role_work_products": [product]}
        intake = derive_event_intake(state, ["site_engineer"])
        self.assertEqual(intake[0]["status"], "RETURNED")
        requirements = build_event_requirements(state, ["site_engineer"])
        self.assertEqual(requirements[0]["status"], "RETURNED")
        self.assertEqual(requirements[0]["feedback"]["required_items"], ["隐蔽验收照片"])

    def test_project_manager_receives_fixed_decision_requirement(self):
        event = {**self.event, "classification": {"event_type": "CONTRACT_REVIEW", "tags": ["合同"]}}
        packet = build_event_requirements({"events": [event], "role_work_products": []}, ["project_manager"])
        self.assertEqual(len(packet), 1)
        self.assertEqual(packet[0]["role"], "project_manager")
        self.assertIn("GO/OPTIMIZE/HOLD/REJECT 判断", packet[0]["deliverables"])


if __name__ == "__main__":
    unittest.main()
