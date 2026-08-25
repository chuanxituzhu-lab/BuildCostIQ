import unittest

from adapters.line_contracts import (
    confirm_line_records,
    line_responsibility,
    mapping_for_confirmed_record,
    preview_line_records,
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


if __name__ == "__main__":
    unittest.main()
