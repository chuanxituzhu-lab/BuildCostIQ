# 市政项目全流程闭环验收

本验收包用于确认一个脱敏的市政道路及雨污水项目可以从资料接入一直走到结算、回款和数字资产交付。它不扩展 Core，也不新增 P10；所有专业事实仍由 P01–P08 维护，P09 只做成果经营投影。

## 一条可执行主链

```text
Project
  → Event
  → Action
  → WorkProduct
  → Evidence
  → Verification
  → Outcome
  → Digital Asset
```

工程事件的状态链和成果状态链同时受守门规则约束：

```text
DISCOVERED → ASSESSED → PLANNING → COMMERCIAL_REVIEW → DECIDED
→ APPROVAL → EXECUTING → VERIFIED → CLAIMING → SETTLEMENT
→ AUDITING → COLLECTION → CLOSED

NOT_FORMED → PHYSICAL_FORMED → EVIDENCE_READY → SUBMITTED
→ CONFIRMED → REVENUE_RECOGNIZED → SETTLED → CASH_REALIZED
```

## 已覆盖的市政流程内容

- 13 个角色工作台，按生产、技术、造价和项目管理边界隔离；
- 统一坐标 `Project + WBS/工程事件 + 位置 + 时间 + 来源`，示例使用道路桩号；
- 生产、技术、造价三线契约，预览后必须由责任人确认才能映射到 Core；
- Action 具备责任人、输入、输出、SLA、复核人和完成标准；
- GO / OPTIMIZE / HOLD / REJECT 决策记录理由、依据和人工确认；
- 数量链：计划 → 实做 → 实测 → 验收 → 商务确认 → 审定 → 支付；
- 材料链：预算 → 采购 → 到货 → 入库 → 领用/退库 → 消耗 → 理论量 → 余料；
- 三层验收：工作成果核验、实体验收、商务验收；
- 外部 CAD/BIM/Office 结果只作为候选数据，必须人工确认；
- 五类黄金场景：地下管线冲突、土方工程量增加、正式设计变更、现场签证、停窝工/工期索赔；
- P09 成果漏斗、六段价值泄漏、异常队列和单一事实源规则；
- 结算交换包使用哈希标识，原始来源和审计关系可回溯。

## 运行验收

在项目根目录执行：

```powershell
cd "F:\造价数字化BuildCostIQ"
.\.venv\Scripts\Activate.ps1
python scripts/verify_municipal_workflow.py
```

预期结果：

```text
municipal workflow: PASSED
PASS  capabilities_p01_p09
PASS  all_facts_accepted
PASS  p08_publishable
PASS  five_golden_scenarios
PASS  event_lifecycle_closed
PASS  outcome_lifecycle_cash_realized
PASS  line_human_confirmed
PASS  collaboration_closed_and_confirmed
PASS  three_level_acceptance
PASS  quantity_chain_complete
PASS  material_chain_complete
PASS  external_candidates_human_confirmed
PASS  p09_no_duplicate_ledger
PASS  p09_closed_queue
PASS  digital_asset_hashed
```

脚本输出的是脱敏演示包，不会自动写入正式项目，也不会替人工确认真实业务数据。真实项目必须逐项通过生产、技术、造价和项目经理的确认门。
