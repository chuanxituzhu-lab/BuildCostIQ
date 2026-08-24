from __future__ import annotations

import unittest

from adapters.evidence_intake import derive_evidence_intake, evidence_intake_snapshot


class EvidenceIntakeTests(unittest.TestCase):
    def test_unique_material_and_document_keys_are_auto_projected_without_p07_write(self):
        product = {
            "product_id": "WP-WH-1",
            "role": "warehouse_officer",
            "product_type": "inventory_movement",
            "fields": {"material_batch": "BATCH-001", "document_ref": "RCV-001", "location": "材料库"},
            "links": {"source_refs": []},
        }
        state = {
            "sources": [{"source_id": "SRC-RCV-001", "name": "RCV-001 入库单 BATCH-001.pdf", "kind": "入库单"}],
            "role_work_products": [product],
            "evidence": {"result": {"links": []}},
        }
        packet = derive_evidence_intake(state, ["warehouse_officer"])
        self.assertEqual(packet[0]["status"], "AUTO_MATCHED")
        self.assertFalse(packet[0]["requires_manual_confirmation"])
        self.assertTrue(packet[0]["candidate_sources"])
        snapshot = evidence_intake_snapshot(state, ["warehouse_officer"])
        self.assertTrue(snapshot["auto_projection"])
        self.assertFalse(snapshot["auto_write_p07"])

    def test_ambiguous_sources_wait_for_human_confirmation(self):
        product = {
            "product_id": "WP-WH-2",
            "role": "warehouse_officer",
            "fields": {"material_batch": "BATCH-002", "document_ref": "RCV-002"},
            "links": {},
        }
        state = {
            "sources": [
                {"source_id": "SRC-A", "name": "RCV-002 BATCH-002 入库单 A.pdf"},
                {"source_id": "SRC-B", "name": "RCV-002 BATCH-002 入库单 B.pdf"},
            ],
            "role_work_products": [product],
        }
        packet = derive_evidence_intake(state, ["warehouse_officer"])
        self.assertEqual(packet[0]["status"], "REVIEW_REQUIRED")
        self.assertTrue(packet[0]["requires_manual_confirmation"])


if __name__ == "__main__":
    unittest.main()
