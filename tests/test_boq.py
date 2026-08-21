import unittest

from core import Evidence, Runtime
from plugins import build_default_plugins
from plugins.boq import (
    BoqParseError,
    parse_merge_boq,
    parse_standard_boq,
)


STANDARD_ROWS = [
    ["序号", "项目编码", "项目名称", "项目特征", "计量单位", "工程量"],
    ["一", "010101001001", "平整场地", "三类土", "m2", 1250.5],
    [None, "措施项目", None, None, None, None],          # section title -> skip
    ["二", "010502001001", "矩形柱", "C30现浇", "m3", "86.4"],  # string qty
    ["", "小计", "", "", "", 1336.9],                      # subtotal -> skip
]


class StandardBoqTests(unittest.TestCase):
    def test_parses_only_valid_coded_rows(self):
        items = parse_standard_boq(STANDARD_ROWS)
        self.assertEqual([i["code"] for i in items], ["010101001001", "010502001001"])
        self.assertEqual(items[1]["quantity"], 86.4)  # string coerced to float

    def test_five_elements_present(self):
        item = parse_standard_boq(STANDARD_ROWS)[0]
        self.assertEqual(set(item), {"code", "name", "feature", "unit", "quantity"})

    def test_missing_required_column_raises(self):
        bad = [["项目编码", "项目名称"], ["010101001001", "平整场地"]]
        with self.assertRaises(BoqParseError):
            parse_standard_boq(bad)

    def test_negative_quantity_rejected(self):
        rows = [STANDARD_ROWS[0], ["一", "010101001001", "平整场地", "", "m2", -5]]
        with self.assertRaises(BoqParseError):
            parse_standard_boq(rows)

    def test_empty_input(self):
        self.assertEqual(parse_standard_boq([]), [])


class MergeBoqTests(unittest.TestCase):
    def test_merge_sums_and_excludes_subtotal(self):
        sheets = {
            "柱": [
                ["构件名称", "体积"],
                ["KZ1", 40.2],
                ["KZ2", 46.2],
                ["小计", 86.4],  # must not be double counted
            ]
        }
        mapping = {"柱": {"code": "010502001001", "name": "矩形柱", "unit": "m3", "quantity_keyword": "体积"}}
        items = parse_merge_boq(sheets, mapping)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 86.4)

    def test_missing_quantity_keyword_raises(self):
        sheets = {"柱": [["构件名称", "数量"], ["KZ1", 4]]}
        mapping = {"柱": {"code": "010502001001", "quantity_keyword": "体积"}}
        with self.assertRaises(BoqParseError):
            parse_merge_boq(sheets, mapping)

    def test_unmapped_sheet_ignored(self):
        sheets = {"梁": [["构件名称", "体积"], ["L1", 10]]}
        mapping = {"柱": {"code": "010502001001", "quantity_keyword": "体积"}}
        self.assertEqual(parse_merge_boq(sheets, mapping), [])


class CapabilityIntegrationTests(unittest.TestCase):
    def test_p02_still_within_frozen_boundary(self):
        runtime = Runtime(build_default_plugins())
        self.assertEqual(runtime.gateway.registered, tuple(f"P{i:02d}" for i in range(1, 10)))

    def test_p02_output_feeds_evidence_model(self):
        runtime = Runtime(build_default_plugins())
        result = runtime.gateway.execute(
            "P02", {"project_id": "demo", "source_id": "s1", "rows": STANDARD_ROWS}
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["item_count"], 2)
        evidence = [
            Evidence("demo", "s1", "boq_item", item) for item in result["items"]
        ]
        with self.assertRaises(TypeError):
            evidence[0].payload["quantity"] = 0

    def test_p02_requires_context(self):
        runtime = Runtime(build_default_plugins())
        with self.assertRaises(ValueError):
            runtime.gateway.execute("P02", {"project_id": "demo"})


if __name__ == "__main__":
    unittest.main()
