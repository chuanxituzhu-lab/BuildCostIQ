import unittest

from core import Runtime
from plugins import build_default_plugins


class FullCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Runtime(build_default_plugins())

    def test_p01_p03_p04_p06_p07_have_real_gateway_results(self):
        common = {"project_id": "full-project", "source_id": "source-1"}
        results = {
            "P01": self.runtime.gateway.execute("P01", {**common, "contract": {"contract_no": "HT-01", "title": "道路施工", "contract_amount": 1000}}),
            "P03": self.runtime.gateway.execute("P03", {**common, "drawings": [{"drawing_no": "A-01", "name": "总平面图"}]}),
            "P04": self.runtime.gateway.execute("P04", {**common, "entries": [{"name": "土方", "quantity": 10, "unit_price": 2}]}),
            "P06": self.runtime.gateway.execute("P06", {**common, "changes": [{"title": "材料调整", "amount": 20}]}),
            "P07": self.runtime.gateway.execute("P07", {**common, "links": [{"target_type": "change", "target_id": "CH-001"}]}),
        }
        self.assertEqual(set(results), {"P01", "P03", "P04", "P06", "P07"})
        self.assertTrue(all(result["status"] == "accepted" for result in results.values()))
        self.assertEqual(results["P04"]["summary"]["baseline_total"], 20.0)
        self.assertEqual(results["P06"]["summary"]["pending_count"], 1)
        self.assertEqual(results["P07"]["summary"]["unverified_count"], 1)


if __name__ == "__main__":
    unittest.main()
