# 全过程项目管理概要：负熵化融合基线

本文件是对 Codex 会话“全过程项目管理概要”的工程化蒸馏结果。它现在由 P09“全过程成果经营管理”承载；P09 只读派生，不改写 P01–P08 的专业事实。

## 1. 顶层定义

> 以工作成果为导向，以工程事件为载体，以造价经营为核心，由生产形成 Fact、技术确认 Validity、造价判断 Value，项目经理对 Outcome 负责；通过三证互证，把工程行为转化为可计量、可确认、可结算、可回款的经营成果。

唯一主链：

```text
Baseline → Event → Decision → Action → Evidence → Outcome → Value Realization
```

其中 `Contract / BOQ / Drawing / Cost Baseline` 继续由 P01–P05 维护；`Change / Signature / Claim / Measurement / Revenue / Settlement / Payment` 继续由 P06–P08 维护。Outcome 只保存关联、状态和系统快照，不创建第二套金额真值。

## 2. 负熵化规则

| 复杂问题 | 最小实现 | 不新增 |
|---|---|---|
| 事情发生了什么 | 一个永久编号 Event | 不按部门拆三套事件 |
| 凭什么证明 | P07 Evidence + 生产/技术/造价三证 | 不另建资料系统 |
| 最终形成什么 | P09 读取 Event 内 `outcome_track` | 不创建第二金额事实源 |
| 价值卡在哪里 | 六段派生 Value Leak | 不人工维护第二套差额账 |
| 谁现在要处理 | 看板 `daily_queue` | 不新增通用 Task/OA |
| 方案为何改变 | Outcome/Event 快照修订 | 不覆盖历史 |
| 现场先干后补 | 现有 `emergency_override` + 审计 | 不为每种异常建专用模块 |

系统铁律：同一事实只录一次；事实源唯一；专业判断不能改写事实；历史只能追加修订；Event 关闭不代表 Outcome 已实现；没有来源就显示待核对。

## 3. Outcome 双状态机

Event 状态机保持不变。Outcome 在同一 Event 内独立推进：

```text
NOT_FORMED → PHYSICAL_FORMED → EVIDENCE_READY → SUBMITTED
            → CONFIRMED → REVENUE_RECOGNIZED → SETTLED → CASH_REALIZED
```

真实项目中的拒绝或放弃使用 `REJECTED / ABANDONED`，必须保留原因。每次快照和状态变化都追加到 `revisions` / `status_history`。

Outcome 类型只保留五类：`PHYSICAL、COMMERCIAL、CONTRACTUAL、SCHEDULE、CASH`。合同权利不是单独的 Core 对象，而是 Commercial Decision 的判断字段和 Outcome 的 `contractual_status`。

## 4. 六段价值泄漏

系统从 Outcome 快照派生，不复制原造价金额：

```text
实体 → 证据完整 → 已申报 → 已确认 → 收入成立 → 已结算 → 已回款
```

对应 `EVIDENCE_LEAK、SUBMISSION_LEAK、CONFIRMATION_LEAK、REVENUE_LEAK、SETTLEMENT_LEAK、CASH_LEAK`。每个差额都能回到 Event、责任节点和原因码；缺少原因时显示“待补充原因”，不猜测。

## 5. 角色边界

- 生产：创建和补充现场 Fact、生产证。
- 技术：形成技术判断、方案和技术证。
- 造价：读取合同/清单/成本事实，形成 Commercial Decision、造价证和 Outcome 快照。
- 项目经理：看经营结果和异常队列，作 GO / OPTIMIZE / HOLD / REJECT 等决策。

金额快照和价值状态的确认仍受角色权限控制；项目经理看到状态、风险和转化率，不看到成本明细。

## 6. 异常路径的最小表达

现实不会总按标准顺序发生，但不能把历史伪装成标准流程。当前采用以下最小表达，不为每种异常新建模块：

- 先干后补/紧急抢险：`emergency_override` + 即时 Evidence + 后补三方判断 + 审计。
- 业主口头指令：保留原始指令证据，权利状态保持 `PENDING`，等待书面确认。
- 方案变化：追加 Event/Outcome 快照修订，不覆盖原技术或经营判断。
- 签证核减、反审、退款：原申报/确认/结算/回款事实分别保留；负向经济事实进入 P06/P08 的调整记录，不把原金额改成负数。
- Event 合并、拆分、取消：使用可追溯的关系或状态记录，原 Event 不删除；若现有 P06/P08 关系不足，再以 Change Request 增补，而不是扩展 P09。
- Outcome 失败：使用 `REJECTED / ABANDONED` 和原因，表示“发生了成本但价值未实现”。

## 7. 五类黄金回归场景

地下管线冲突、土方工程量增加、正式设计变更、现场签证、停窝工/工期索赔都应沿同一主链运行。差异只体现在 Event 类型、Business Reference 和 Outcome 类型，不再增加新的 Core 对象。

## 8. 当前实现入口

- Core：`core/event_kernel.py` 的 `outcome_track`、`transition_outcome`、`record_outcome_snapshot`、`compute_value_leaks`。
- Web API：`POST /api/event-kernel/outcome`，支持快照追加和受控状态迁移。
- 看板：`GET /api/dashboard` 的 `outcome_management`，包含成果漏斗、价值泄漏和只显示异常的 `daily_queue`。
- WebUI：工程事件卡片可查看成果状态；造价经理可追加 Outcome 快照；经营看板展示成果转化漏斗和价值泄漏。

后续需求优先用字段、规则、适配器或配置解决。只有真实项目反复证明现有对象无法表达，才提交 Core Change Request；不得因为未来的多项目、企业标准库、OA、HR、仓储或通用任务管理提前扩 Core。
