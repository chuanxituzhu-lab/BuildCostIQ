import unittest
from decimal import Decimal

from core import Runtime
from plugins import build_default_plugins
from plugins.basis import COMPARABLE, CONFLICTED, UNDECLARED, PriceBasis, comparable
from plugins.boq import find_header_row, parse_standard_boq
from plugins.costplan import plan_costs
from plugins.normalize import UnitError, normalize_unit, unit_factor, units_comparable
from plugins.review import SEVERITY_BLOCK, SEVERITY_WARN, review_boq


CONTRACT_BASIS = PriceBasis("tax_exclusive", "winning_bid", "HT-2026-001", "2026-01")
MARKET_SAME_TAX = PriceBasis("tax_exclusive", "market_quote", "询价单-07", "2026-06")
MARKET_OTHER_TAX = PriceBasis("tax_inclusive", "market_quote", "询价单-07", "2026-06")


class UnitNormalizationTests(unittest.TestCase):
    def test_common_writings_fold_to_one_symbol(self):
        for raw in ("㎡", "m²", "平方米", "平米", " M2 "):
            self.assertEqual(normalize_unit(raw), "m2")

    def test_quota_multiplier_prefix_is_parsed(self):
        self.assertEqual(unit_factor("100m3", "m3"), Decimal("100"))
        self.assertEqual(unit_factor("10m2", "m2"), Decimal("10"))

    def test_cross_dimension_units_are_refused(self):
        with self.assertRaises(UnitError):
            unit_factor("m2", "m3")
        self.assertFalse(units_comparable("个", "m"))

    def test_mass_conversion(self):
        self.assertEqual(unit_factor("吨", "kg"), Decimal("1000"))


class PriceBasisTests(unittest.TestCase):
    def test_same_tax_basis_is_comparable(self):
        self.assertEqual(comparable(CONTRACT_BASIS, MARKET_SAME_TAX)[0], COMPARABLE)

    def test_tax_conflict_is_refused(self):
        status, reason = comparable(CONTRACT_BASIS, MARKET_OTHER_TAX)
        self.assertEqual(status, CONFLICTED)
        self.assertIn("税制", reason)

    def test_missing_declaration_is_not_the_same_as_conflict(self):
        self.assertEqual(comparable(CONTRACT_BASIS, None)[0], UNDECLARED)
        self.assertEqual(comparable(PriceBasis("", "", ""), CONTRACT_BASIS)[0], UNDECLARED)


class CostPlanBasisGateTests(unittest.TestCase):
    ITEMS = [{"code": "010502001001", "quantity": "10", "unit": "m3"}]
    CONTRACT = {"010502001001": "500"}
    MARKET = {"010502001001": "450"}

    def test_conflicting_basis_yields_no_variance_number(self):
        plan = plan_costs(
            self.ITEMS, self.CONTRACT, self.MARKET,
            contract_basis=CONTRACT_BASIS, market_basis=MARKET_OTHER_TAX,
        )
        control = plan["cost_control"]
        self.assertEqual(control["comparability"], CONFLICTED)
        self.assertIsNone(control["total_variance"])
        self.assertEqual(control["items"], [])

    def test_comparable_basis_yields_variance(self):
        plan = plan_costs(
            self.ITEMS, self.CONTRACT, self.MARKET,
            contract_basis=CONTRACT_BASIS, market_basis=MARKET_SAME_TAX,
        )
        self.assertEqual(plan["cost_control"]["comparability"], COMPARABLE)
        self.assertEqual(plan["cost_control"]["total_variance"], 500.0)

    def test_external_summary_is_untouched_by_the_gate(self):
        plan = plan_costs(
            self.ITEMS, self.CONTRACT, self.MARKET,
            contract_basis=CONTRACT_BASIS, market_basis=MARKET_OTHER_TAX,
        )
        self.assertEqual(plan["summary"]["contract_subtotal"], 5000.0)


class HeaderDetectionTests(unittest.TestCase):
    BANNERED = [
        ["某市政道路工程 分部分项工程量清单", None, None, None, None, None],
        ["标段：SG-02", None, None, None, None, None],
        ["序号", "项目编码", "项目名称", "项目特征", "计量单位", "工程量"],
        ["1", "040202002001", "石灰稳定土", "12%灰土", "m3", 880.0],
    ]

    def test_header_below_banner_rows_is_found(self):
        self.assertEqual(find_header_row(self.BANNERED), 2)

    def test_items_parse_despite_banner(self):
        items = parse_standard_boq(self.BANNERED)
        self.assertEqual([i["code"] for i in items], ["040202002001"])
        self.assertEqual(items[0]["quantity"], 880.0)


class ReviewRuleTests(unittest.TestCase):
    def test_amount_mismatch_blocks_publication(self):
        rows = [{"code": "040202002001", "name": "石灰稳定土", "unit": "m3",
                 "quantity": "100", "price": "85.50", "total": "8000.00"}]
        result = review_boq(rows)
        codes = {f["rule_id"] for f in result["findings"]}
        self.assertIn("R-AMT-01", codes)
        self.assertFalse(result["publishable"])

    def test_amount_within_rounding_tolerance_passes(self):
        rows = [{"code": "040202002001", "name": "石灰稳定土", "unit": "m3",
                 "quantity": "100", "price": "85.50", "total": "8550.01"}]
        self.assertTrue(review_boq(rows)["publishable"])

    def test_negative_quantity_blocks(self):
        rows = [{"code": "040202002001", "name": "x", "unit": "m3", "quantity": "-5"}]
        self.assertIn("R-QTY-01", {f["rule_id"] for f in review_boq(rows)["findings"]})

    def test_duplicate_twelve_digit_code_blocks(self):
        rows = [
            {"code": "040202002001", "name": "a", "unit": "m3", "quantity": "1"},
            {"code": "040202002001", "name": "b", "unit": "m3", "quantity": "2"},
        ]
        self.assertIn("R-CODE-02", {f["rule_id"] for f in review_boq(rows)["findings"]})

    def test_nine_digit_repeat_is_not_an_error(self):
        rows = [
            {"code": "040202002", "name": "a", "unit": "m3", "quantity": "1"},
            {"code": "040202002", "name": "b", "unit": "m3", "quantity": "2"},
        ]
        self.assertNotIn("R-CODE-02", {f["rule_id"] for f in review_boq(rows)["findings"]})

    def test_incomparable_unit_blocks(self):
        rows = [{"code": "040202002001", "name": "石灰稳定土", "unit": "m2", "quantity": "10"}]
        result = review_boq(rows, reference_units={"040202002001": "m3"})
        self.assertIn("R-UNIT-01", {f["rule_id"] for f in result["findings"]})

    def test_multiplier_unit_is_warned_not_blocked(self):
        rows = [{"code": "040202002001", "name": "石灰稳定土", "unit": "100m3", "quantity": "10"}]
        result = review_boq(rows, reference_units={"040202002001": "m3"})
        finding = next(f for f in result["findings"] if f["rule_id"] == "R-UNIT-02")
        self.assertEqual(finding["severity"], SEVERITY_WARN)
        self.assertTrue(result["publishable"])

    def test_price_rules_suppressed_when_basis_conflicts(self):
        rows = [{"code": "040202002001", "name": "x", "unit": "m3",
                 "quantity": "1", "price": "1000"}]
        result = review_boq(
            rows,
            reference_prices={"040202002001": "100"},
            subject_basis=CONTRACT_BASIS,
            reference_basis=MARKET_OTHER_TAX,
        )
        rule_ids = {f["rule_id"] for f in result["findings"]}
        self.assertIn("R-BAS-01", rule_ids)
        self.assertNotIn("R-PRC-01", rule_ids)   # 口径不通，不出偏差结论
        self.assertFalse(result["summary"]["price_rules_applied"])

    def test_price_deviation_reported_when_basis_is_sound(self):
        rows = [{"code": "040202002001", "name": "x", "unit": "m3",
                 "quantity": "1", "price": "1000"}]
        result = review_boq(
            rows,
            reference_prices={"040202002001": "100"},
            subject_basis=CONTRACT_BASIS,
            reference_basis=MARKET_SAME_TAX,
        )
        self.assertIn("R-PRC-01", {f["rule_id"] for f in result["findings"]})

    def test_no_reference_means_no_invented_judgement(self):
        rows = [{"code": "040202002001", "name": "x", "unit": "m3",
                 "quantity": "1", "price": "999999"}]
        rule_ids = {f["rule_id"] for f in review_boq(rows)["findings"]}
        self.assertNotIn("R-PRC-01", rule_ids)
        self.assertNotIn("R-UNIT-01", rule_ids)
        self.assertNotIn("R-QTY-03", rule_ids)

    def test_every_finding_carries_evidence(self):
        rows = [{"code": "BAD", "name": "", "unit": "m3", "quantity": "-1"}]
        for finding in review_boq(rows)["findings"]:
            self.assertTrue(finding["evidence"], finding)

    def test_coverage_uses_caller_supplied_divisions(self):
        rows = [{"code": "040202002001", "name": "x", "unit": "m3", "quantity": "1"}]
        result = review_boq(rows, expected_divisions=[("0401", "土石方工程"), ("0402", "道路工程")])
        messages = [f["message"] for f in result["findings"] if f["rule_id"] == "R-COV-01"]
        self.assertEqual(len(messages), 1)
        self.assertIn("土石方工程", messages[0])


class P08IntegrationTests(unittest.TestCase):
    def test_p08_is_registered_within_the_frozen_boundary(self):
        runtime = Runtime(build_default_plugins())
        self.assertEqual(runtime.gateway.registered, tuple(f"P{i:02d}" for i in range(1, 10)))

    def test_p08_traversable_with_bare_context(self):
        runtime = Runtime(build_default_plugins())
        result = runtime.gateway.execute("P08", {"project_id": "demo", "source_id": "s1"})
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["publishable"])
        self.assertEqual(result["findings"], [])

    def test_p08_reports_blocking_finding_through_the_gateway(self):
        runtime = Runtime(build_default_plugins())
        result = runtime.gateway.execute("P08", {
            "project_id": "demo",
            "source_id": "s1",
            "rows": [{"code": "040202002001", "name": "x", "unit": "m3",
                      "quantity": "2", "price": "100", "total": "500"}],
        })
        self.assertFalse(result["publishable"])
        self.assertEqual(result["summary"][SEVERITY_BLOCK], 1)

    def test_p08_requires_project_context(self):
        runtime = Runtime(build_default_plugins())
        with self.assertRaises(ValueError):
            runtime.gateway.execute("P08", {"project_id": "demo"})


if __name__ == "__main__":
    unittest.main()
