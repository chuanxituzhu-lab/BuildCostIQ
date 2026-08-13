"""P02 → P05 → P08 端到端演示（市政道路场景，数据为脱敏样例）。

运行：``python examples/review_workflow.py``

演示三件事：
1. 表头不在第一行的清单照样能解析（真实导出文件的常态）。
2. 合同价册与市场价册税制口径冲突时，P05 拒绝出偏差数。
3. P08 用确定性规则抓出合价错误与单位错配，并给出发布闸门结论。
"""

from core import Evidence, Runtime
from plugins import build_default_plugins
from plugins.boq import parse_standard_boq

# 表头压在第 3 行 —— 上面是工程名称与标段行。
RAW_SHEET = [
    ["某市政道路改造工程 分部分项工程量清单", None, None, None, None, None],
    ["标段：SG-02   编制单位：××市政设计院", None, None, None, None, None],
    ["序号", "项目编码", "项目名称", "项目特征", "计量单位", "工程量"],
    ["1", "040202002001", "石灰稳定土", "12%灰土 厚30cm", "m3", 880.0],
    ["2", "040203006001", "沥青混凝土面层", "AC-13C 厚4cm", "㎡", 12600.0],
    ["", "小计", "", "", "", 13480.0],
]

CONTRACT_PRICES = {"040202002001": "128.60", "040203006001": "96.40"}
MARKET_PRICES = {"040202002001": "121.00", "040203006001": "103.20"}

CONTRACT_BASIS = {
    "tax_inclusion": "tax_exclusive",
    "price_type": "winning_bid",
    "source": "HT-2026-001",
    "price_date": "2026-01",
}
# 注意：这本市场价册是含税价 —— 与合同的除税价不可相减。
MARKET_BASIS = {
    "tax_inclusion": "tax_inclusive",
    "price_type": "market_quote",
    "source": "询价单-2026-07",
    "price_date": "2026-07",
}

# 待审的报价行：第 1 行合价算错，第 2 行单位写成了 m3。
REVIEW_ROWS = [
    {"row": 4, "code": "040202002001", "name": "石灰稳定土", "unit": "m3",
     "quantity": "880", "price": "128.60", "total": "113000.00"},
    {"row": 5, "code": "040203006001", "name": "沥青混凝土面层", "unit": "m3",
     "quantity": "12600", "price": "96.40", "total": "1214640.00"},
]

REFERENCE_UNITS = {"040202002001": "m3", "040203006001": "m2"}


def main() -> None:
    runtime = Runtime(build_default_plugins())
    project_id, source_id = "demo-road-2026", "sanitized-boq"

    items = parse_standard_boq(RAW_SHEET)
    print(f"[P02] 解析出清单项 {len(items)} 条（表头自动定位在第 3 行）")
    for item in items:
        print(f"       {item['code']}  {item['name']}  {item['quantity']} {item['unit']}")

    plan = runtime.gateway.execute("P05", {
        "project_id": project_id,
        "source_id": source_id,
        "items": items,
        "contract_prices": CONTRACT_PRICES,
        "market_prices": MARKET_PRICES,
        "contract_basis": CONTRACT_BASIS,
        "market_basis": MARKET_BASIS,
    })
    print(f"\n[P05] 合同口径小计 = {plan['summary']['contract_subtotal']}"
          f"  待组价 {plan['summary']['pending_item_count']} 条")
    control = plan["cost_control"]
    print(f"       成本控制：{control['comparability']} — {control['reason'] or '口径一致'}")
    print(f"       偏差合计：{control['total_variance']}")

    review = runtime.gateway.execute("P08", {
        "project_id": project_id,
        "source_id": source_id,
        "rows": REVIEW_ROWS,
        "reference_units": REFERENCE_UNITS,
        "reference_prices": MARKET_PRICES,
        "subject_basis": CONTRACT_BASIS,
        "reference_basis": MARKET_BASIS,
    })
    print(f"\n[P08] 发现 {review['summary']['finding_count']} 条  "
          f"block={review['summary']['block']} warn={review['summary']['warn']} "
          f"info={review['summary']['info']}")
    for finding in review["findings"]:
        line = f"行{finding['row']}" if finding["row"] else "全局"
        print(f"       [{finding['severity']:<5}] {finding['rule_id']} {line}  {finding['message']}")
        print(f"               依据：{finding['evidence']}")

    print(f"\n[闸门] 允许发布：{review['publishable']}")

    evidence = [
        Evidence(project_id=project_id, source_id=source_id, kind="review_finding", payload=finding)
        for finding in review["findings"]
    ]
    print(f"[存证] 生成 Evidence 记录 {len(evidence)} 条")


if __name__ == "__main__":
    main()
