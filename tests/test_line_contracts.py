import unittest

from adapters.line_contracts import (
    confirm_line_records,
    line_responsibility,
    mapping_for_confirmed_record,
    preview_line_records,
    role_flow_contracts,
    role_workbench_contracts,
)


class ResponsibilityLineTests(unittest.TestCase):
    def test_responsibility_is_automatic_and_only_line_head_can_confirm(self):
        preview = preview_line_records(
            "production",
            "project-1",
            [{
                "record_id": "PROD-1",
                "event_id": "EV-1",
                "occurred_at": "2026-08-21T09:00:00+00:00",
                "actor": "site-engineer-1",
                "status": "COMPLETED",
                "progress": 100,
                "evidence_refs": ["PHOTO-1"],
            }],
        )
        self.assertEqual(preview["responsibility"]["head_role"], "production_manager")
        self.assertEqual(preview["records"][0]["responsibility"]["assignment_mode"], "AUTOMATIC_POLICY")

        with self.assertRaises(PermissionError):
            confirm_line_records(preview, {"username": "cost-1", "role": "cost_manager"})

        confirmed = confirm_line_records(
            preview,
            {"username": "production-manager-1", "role": "production_manager"},
        )
        self.assertEqual(confirmed["responsibility"]["assigned_to"], "production-manager-1")
        mapping = mapping_for_confirmed_record(
            "production",
            confirmed["records"][0],
            {"username": "production-manager-1", "role": "production_manager"},
        )
        self.assertEqual(mapping["responsibility"]["head_role"], "production_manager")
        self.assertEqual(mapping["targets"]["production_track"]["owner"], "production-manager-1")

    def test_all_three_lines_have_one_fixed_department_head(self):
        self.assertEqual(line_responsibility("production")["head_role"], "production_manager")
        self.assertEqual(line_responsibility("technical")["head_role"], "technical_lead")
        self.assertEqual(line_responsibility("cost")["head_role"], "cost_manager")

    def test_role_flow_keeps_cost_core_and_handoff_boundaries(self):
        contract = role_flow_contracts()
        self.assertEqual(contract["version"], "1.0")
        roles = contract["roles"]
        self.assertTrue({"technical_lead", "production_manager", "cost_manager"}.issubset(
            roles["project_manager"]["next_roles"]
        ))
        self.assertIn("technical_lead", roles["cost_manager"]["escalates_to"])
        self.assertIn("production_manager", roles["technical_lead"]["next_roles"])
        self.assertIn("cost_manager", roles["production_manager"]["next_roles"])
        self.assertIn("technical_conclusion", roles["cost_manager"]["cannot_change"])
        self.assertIn("production_fact", roles["cost_manager"]["cannot_change"])
        self.assertIn("cost_fact", roles["production_manager"]["cannot_change"])

    def test_every_role_has_distinct_work_product_contract_and_handoffs(self):
        catalog = role_workbench_contracts()
        self.assertEqual(catalog["version"], "1.0")
        roles = catalog["roles"]
        expected = {
            "warehouse_officer": "inventory_movement",
            "site_engineer": "site_fact",
            "surveyor": "survey_result",
            "lab_testing_officer": "lab_test_result",
            "quality_officer": "quality_acceptance",
            "document_controller": "document_archive",
        }
        for role, product_type in expected.items():
            self.assertEqual(roles[role]["product_type"], product_type)
            self.assertGreaterEqual(len(roles[role]["input_fields"]), 4)
            self.assertTrue(roles[role]["outputs"])
            self.assertTrue(roles[role]["collaboration"]["hands_to"])
        self.assertNotEqual(roles["warehouse_officer"]["product_type"], roles["procurement_officer"]["product_type"])
        self.assertNotEqual(roles["site_engineer"]["product_type"], roles["surveyor"]["product_type"])
        self.assertIn("cost_manager", roles["warehouse_officer"]["collaboration"]["hands_to"])
        self.assertIn("quality_officer", roles["lab_testing_officer"]["collaboration"]["hands_to"])


if __name__ == "__main__":
    unittest.main()
