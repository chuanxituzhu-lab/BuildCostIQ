import tempfile
import unittest
from pathlib import Path

from adapters.municipal_workflow import MUNICIPAL_ROLES, persist_municipal_demo, run_municipal_workflow
from adapters.workspace import LocalProjectWorkspace


class MunicipalWorkflowAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_municipal_workflow("municipal-test-project")

    def test_one_project_runs_all_frozen_capabilities_and_closes(self):
        self.assertEqual(self.result["status"], "PASSED")
        self.assertTrue(all(self.result["checks"].values()))
        self.assertEqual(len(self.result["events"]), 5)
        self.assertEqual(self.result["p09"]["summary"]["open_event_count"], 0)

    def test_municipal_roles_are_isolated_workbenches(self):
        workbenches = self.result["work_products"]["role_workbenches"]
        self.assertEqual(set(workbenches), set(MUNICIPAL_ROLES))
        self.assertTrue(all(item["isolated"] for item in workbenches.values()))

    def test_human_confirmation_and_three_acceptance_layers_are_required(self):
        self.assertTrue(self.result["checks"]["line_human_confirmed"])
        self.assertTrue(self.result["checks"]["collaboration_closed_and_confirmed"])
        review = self.result["work_products"]["work_product"]["review"]
        self.assertEqual(review["work_product_verification"], "PASS")
        self.assertEqual(review["physical_acceptance"], "PASS")
        self.assertEqual(review["commercial_acceptance"], "PASS")

    def test_quantity_material_and_digital_asset_chains_are_traceable(self):
        product = self.result["work_products"]["work_product"]
        self.assertEqual(product["quantity_chain"]["planned"], 500)
        self.assertEqual(product["quantity_chain"]["paid"], 562)
        self.assertEqual(product["material_chain"]["remaining"], 5)
        asset = self.result["work_products"]["digital_asset"]
        self.assertTrue(asset["immutable"])
        self.assertEqual(len(asset["content_hash"]), 64)

    def test_validated_packet_can_be_persisted_for_webui_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            state = persist_municipal_demo(self.result, LocalProjectWorkspace(Path(directory)))
            self.assertEqual(state["project"]["id"], "municipal-test-project")
            self.assertEqual(len(state["events"]), 5)
            self.assertEqual(state["events"][0]["status"], "CLOSED")
            self.assertEqual(state["golden_scenario"]["acceptance"]["p09_closed_queue"], True)


if __name__ == "__main__":
    unittest.main()
