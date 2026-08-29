from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CostLoopFocusTests(unittest.TestCase):
    def test_default_registration_exposes_only_three_core_users(self):
        html = (ROOT / "gui" / "static" / "index.html").read_text(encoding="utf-8")
        select = html.split('<select id="registerRole">', 1)[1].split("</select>", 1)[0]

        self.assertEqual(select.count("<option"), 3)
        self.assertIn('value="project_manager"', select)
        self.assertIn('value="cost_manager"', select)
        self.assertIn('value="cost_estimator"', select)
        self.assertNotIn('value="technical_lead"', select)

    def test_product_scope_keeps_tools_outside_the_cost_core(self):
        scope = (ROOT / "docs" / "COST_LOOP_CORE.md").read_text(encoding="utf-8")

        self.assertIn("不新增第二金额账", scope)
        self.assertIn("CAD 工程量计算", scope)
        self.assertIn("工程施工项目岗位成果管理", scope)

    def test_audit_workflow_defines_traceable_settlement_gates(self):
        text = (ROOT / "docs" / "COST_DELIVERABLE_AUDIT_WORKFLOW.md").read_text(encoding="utf-8")
        for marker in (
            "施工项目造价不是所有工程事实的生产者",
            "G0 合同闸门",
            "G6 结算支付闸门",
            "Engineering Event Packet",
            "已记录 ≠ 已批准 ≠ 可计量 ≠ 已结算 ≠ 已收款",
            "金额事实只保留一处",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
