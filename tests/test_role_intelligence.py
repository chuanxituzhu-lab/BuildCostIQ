from __future__ import annotations

import unittest

from adapters.role_intelligence import ROLE_DEPARTMENT_HEADS, derive_role_alerts, role_intelligence_snapshot


class RoleIntelligenceTests(unittest.TestCase):
    def test_every_role_has_independent_owner_and_fixed_streams(self):
        snapshot = role_intelligence_snapshot({"role_work_products": []})
        self.assertEqual(set(snapshot["contracts"]), set(ROLE_DEPARTMENT_HEADS))
        for role, contract in snapshot["contracts"].items():
            self.assertTrue(contract["department"])
            self.assertTrue(contract["head_role"])
            self.assertIsInstance(contract["inputs"], list)
            self.assertIsInstance(contract["hands_to"], list)
            self.assertTrue(snapshot["single_source_of_truth"])

    def test_warehouse_cross_line_red_lines_are_derived_without_guessing(self):
        state = {
            "role_work_products": [
                {
                    "product_id": "WP-WH",
                    "role": "warehouse_officer",
                    "fields": {
                        "material_batch": "MAT-001",
                        "inventory_after": "-2",
                        "check_status": "EXCEPTION",
                    },
                    "links": {"event_id": "EV-1", "evidence_refs": ["E-1"]},
                },
                {
                    "product_id": "WP-LAB",
                    "role": "lab_testing_officer",
                    "fields": {"material_batch": "MAT-001", "pass_status": "FAIL"},
                    "links": {"event_id": "EV-1", "evidence_refs": ["E-2"]},
                },
            ]
        }
        alerts = derive_role_alerts(state, ["warehouse_officer"])
        codes = {item["code"] for item in alerts}
        self.assertIn("INVENTORY_NEGATIVE", codes)
        self.assertIn("WAREHOUSE_EXCEPTION", codes)
        self.assertIn("TEST_BATCH_FAIL", codes)
        self.assertTrue(all(item["human_confirmation_required"] for item in alerts))
        self.assertTrue(all(item["derived_only"] for item in alerts))

    def test_missing_event_is_scoped_to_the_originating_role(self):
        state = {
            "role_work_products": [
                {
                    "product_id": "WP-SITE",
                    "role": "site_engineer",
                    "fields": {"wbs": "WBS-1", "location": "K1", "progress_qty": 10},
                    "links": {"event_id": "", "evidence_refs": []},
                }
            ]
        }
        alerts = derive_role_alerts(state, ["site_engineer"])
        self.assertEqual({item["role"] for item in alerts}, {"site_engineer"})
        self.assertEqual({item["code"] for item in alerts}, {"MISSING_EVENT", "MISSING_EVIDENCE"})

    def test_material_baseline_drives_procurement_and_warehouse_red_lines(self):
        state = {
            "baseline": {"result": {"entries": [{"code": "MAT-001", "quantity": 100}]}},
            "role_work_products": [
                {
                    "product_id": "WP-PO",
                    "role": "procurement_officer",
                    "fields": {"material_code": "MAT-001", "requested_qty": 120},
                    "links": {"event_id": "EV-1", "evidence_refs": ["E-PO"]},
                },
                {
                    "product_id": "WP-WH-1",
                    "role": "warehouse_officer",
                    "fields": {"movement_type": "ISSUE", "material_batch": "MAT-001", "quantity": 115, "inventory_after": 0},
                    "links": {"event_id": "EV-1", "evidence_refs": ["E-WH"]},
                },
            ],
        }
        alerts = derive_role_alerts(state)
        codes = {(item["role"], item["code"]) for item in alerts}
        self.assertIn(("procurement_officer", "PURCHASE_BASELINE_OVER_REDLINE"), codes)
        self.assertIn(("warehouse_officer", "QUANTITY_OVER_REDLINE"), codes)
        ids = [item["alert_id"] for item in alerts]
        self.assertEqual(ids, [item["alert_id"] for item in derive_role_alerts(state)])


if __name__ == "__main__":
    unittest.main()
