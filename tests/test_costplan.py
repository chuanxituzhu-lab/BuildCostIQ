import unittest

from core import Evidence, Runtime
from plugins import build_default_plugins
from plugins.costplan import (
    STATUS_CONTRACT,
    STATUS_PENDING,
    CostPlanError,
    plan_costs,
    summarize_resources,
)


BOQ_ITEMS = [
    {"code": "010502001001", "name": "矩形柱", "unit": "m3", "quantity": 86.4},
    {"code": "010402001001", "name": "砌块墙", "unit": "m3", "quantity": 210.0},
    {"code": "010101099001", "name": "新增支护", "unit": "m3", "quantity": 50.0},  # no contract rate
]
CONTRACT = {"010502001001": 620.50, "010402001001": 310.00}
MARKET = {"010502001001": 580.00, "010402001001": 295.00}


class ResourceSummaryTests(unittest.TestCase):
    def test_labor_material_machinery_stay_separate_and_compare_bid_market(self):
        result = summarize_resources([
            {"resource_type": "labor", "name": "普工", "quantity": 10, "bid_unit_price": 180, "market_unit_price": 200},
            {"resource_type": "material", "name": "混凝土", "quantity": 20, "bid_unit_price": 420, "market_unit_price": 390},
            {"resource_type": "machinery", "name": "挖掘机", "quantity": 2, "bid_unit_price": 1200, "market_unit_price": 1100},
        ])
        self.assertTrue(result["complete"])
        self.assertEqual(result["item_count"], 3)
        self.assertEqual({item["resource_type"] for item in result["groups"]}, {"labor", "material", "machinery"})
        material = next(item for item in result["groups"] if item["resource_type"] == "material")
        self.assertEqual(material["variance"], 600.0)


class ContractPricingTests(unittest.TestCase):
    def test_contract_items_priced_at_winning_bid(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT)
        col = plan["items"][0]
        self.assertEqual(col["status"], STATUS_CONTRACT)
        self.assertEqual(col["unit_price"], 620.50)
        self.assertEqual(col["amount"], round(86.4 * 620.50, 2))
        self.assertEqual(col["price_basis"], "winning-bid")

    def test_contract_subtotal_is_exact(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT)
        expected = round(86.4 * 620.50 + 210.0 * 310.00, 2)
        self.assertEqual(plan["summary"]["contract_subtotal"], expected)
        self.assertEqual(plan["summary"]["contract_item_count"], 2)

    def test_money_rounding_half_up(self):
        # 0.005 * 1 should round to 0.01 (half-up), not 0.00 (bankers).
        plan = plan_costs([{"code": "X", "quantity": 1}], {"X": 0.005})
        self.assertEqual(plan["items"][0]["amount"], 0.01)


class PendingItemTests(unittest.TestCase):
    def test_missing_item_is_flagged_not_guessed(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT)
        pending = [r for r in plan["items"] if r["status"] == STATUS_PENDING]
        self.assertEqual(len(pending), 1)
        self.assertIsNone(pending[0]["unit_price"])
        self.assertEqual(pending[0]["amount"], 0.0)

    def test_pending_kept_separate_from_contract_total(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT)
        s = plan["summary"]
        self.assertEqual(s["pending_item_count"], 1)
        self.assertEqual(s["pending_subtotal"], 0.0)
        # contract subtotal must not include the pending item
        self.assertEqual(s["contract_subtotal"], round(86.4 * 620.50 + 210.0 * 310.00, 2))

    def test_missing_code_raises(self):
        with self.assertRaises(CostPlanError):
            plan_costs([{"quantity": 5}], CONTRACT)

    def test_negative_contract_price_raises(self):
        with self.assertRaises(CostPlanError):
            plan_costs(BOQ_ITEMS, {"010502001001": -1})


class MarketIsolationTests(unittest.TestCase):
    def test_market_price_never_enters_external_numbers(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT, MARKET)
        external_prices = [r.get("unit_price") for r in plan["items"]]
        self.assertNotIn(580.00, external_prices)
        self.assertNotIn(295.00, external_prices)
        # summary carries no market figure
        self.assertNotIn(580.00, plan["summary"].values())

    def test_cost_control_variance_is_correct(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT, MARKET)
        cc = plan["cost_control"]
        expected = round((620.50 - 580.00) * 86.4 + (310.00 - 295.00) * 210.0, 2)
        self.assertEqual(cc["total_variance"], expected)

    def test_no_market_book_means_no_cost_control(self):
        plan = plan_costs(BOQ_ITEMS, CONTRACT)
        self.assertIsNone(plan["cost_control"])


class CapabilityIntegrationTests(unittest.TestCase):
    def test_p05_within_frozen_boundary(self):
        runtime = Runtime(build_default_plugins())
        self.assertEqual(runtime.gateway.registered, tuple(f"P{i:02d}" for i in range(1, 10)))

    def test_p05_traversable_with_bare_context(self):
        runtime = Runtime(build_default_plugins())
        result = runtime.gateway.execute("P05", {"project_id": "p", "source_id": "s"})
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["summary"]["total_item_count"], 0)

    def test_p02_to_p05_pipeline_feeds_evidence(self):
        runtime = Runtime(build_default_plugins())
        rows = [
            ["项目编码", "项目名称", "计量单位", "工程量"],
            ["010502001001", "矩形柱", "m3", 86.4],
        ]
        boq = runtime.gateway.execute("P02", {"project_id": "p", "source_id": "s", "rows": rows})
        plan = runtime.gateway.execute(
            "P05",
            {"project_id": "p", "source_id": "s", "items": boq["items"], "contract_prices": CONTRACT},
        )
        self.assertEqual(plan["summary"]["contract_item_count"], 1)
        evidence = [Evidence("p", "s", "cost_plan_item", r) for r in plan["items"]]
        with self.assertRaises(TypeError):
            evidence[0].payload["amount"] = 0


if __name__ == "__main__":
    unittest.main()
