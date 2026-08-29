# BuildCostIQ 造价闭环 Agent 核心边界

## Build Decision Record

- **Idea / real task:** 将 BuildCostIQ 从全岗位综合项目工作台收敛为施工项目造价闭环 Agent，主要服务项目经理、造价经理和造价员。
- **Closest existing projects or capabilities:** 当前仓库已有 Core Engineering Event Kernel、P01–P09、岗位成果接口和本地 WebUI；外部已有综合施工 ERP、CAD/PDF 算量与岗位成果工具。
- **Step 0 decision:** **Improve**。
- **Measurable improvement or differentiator:** 默认直接用户从 14 个岗位收敛为 3 个核心角色；首次入口不再展示非造价岗位；保持一个金额事实源；CAD/岗位成果通过适配边界接入而不扩张 Core。
- **Success measure and required evidence:** 首页与首次注册只呈现项目经理、造价经理、造价员；现有角色数据和 API 继续兼容；发布校验与聚焦测试通过。
- **Minimum Core:** Project、Source、Engineering Event、Evidence、Quantity/Price/Baseline、Change/Measurement/Settlement、Outcome、人工确认和审计。
- **Plugin boundaries:** CAD 算量、岗位成果管理、识别、外部依据和未来专业工具只输出带来源、版本、项目、WBS/位置和证据引用的数据包；插件不能直接改写金额事实。
- **Local-first boundary:** 确定性解析、规则、状态、证据和存储默认本地执行；外部识别仍需逐文件明确同意。
- **Data classification and local trust boundary:** 项目代码与运行数据均按 Internal/Unknown 处理；凭据、人员、合同、价格、项目资料属于 Sensitive/Restricted，留在本地数据根目录。
- **GitHub/public release decision:** **Blocked**；本次未获得公开发布授权，也未执行发布。
- **External transfer plan:** 无。只做本地代码、文档和测试。
- **State, change signals, and next-check rule:** Event/Outcome 状态变化、证据缺口、量价偏差和人工决策触发复核；稳定状态不轮询。
- **Observation / inference / hypothesis / fact boundary:** 工具输出和资料提取先作为 Observation；规则计算为 Inference；未经核验的异常为 Hypothesis；只有来源、口径和人工确认齐备后才成为 Fact。
- **Evolution, validation, canary, version, and rollback plan:** 先收敛入口和定位，不删除兼容能力；通过静态 UI 契约与现有回归测试验证；单次提交可整体回滚。
- **WebUI decision:** **Required**；项目经理需要看板，造价经理和造价员需要可视化录入、审核和证据追踪。
- **Default WebUI path:** Open → 选择项目/导入资料 → 执行造价闭环 → 查看结果/异常 → 人工确认。
- **Simplest reliable implementation:** 保留现有 Core、P01–P09 和权限实现，只调整产品入口、说明与插件边界。
- **Explicitly not building:** 不建设综合 OA、进度计划、物资仓储、质量安全或 CAD 编辑器；不复制岗位成果系统；不在 Core 内实现 CAD 算量；不新增第二金额账。

## 产品一句话

BuildCostIQ 是施工项目的本地造价闭环 Agent：把合同、清单、图纸版本、工程量、价格、变更、计量、结算、证据和回款沿同一工程事件串成可复核闭环。

施工全过程的成果清单、七道审计闸门和主工作流见 [COST_DELIVERABLE_AUDIT_WORKFLOW.md](COST_DELIVERABLE_AUDIT_WORKFLOW.md)。

## 三类核心用户

| 用户 | 默认工作面 | 最终责任 |
| --- | --- | --- |
| 项目经理 | 经营看板、异常队列、成果转化、决策与升级 | 看结果、定责任、配资源、确认决策 |
| 造价经理 | 合同基准、目标成本、变更、计量、结算、证据与 Outcome | 守金额口径和商业闸门，完成造价总审 |
| 造价员 | 清单、工程量、组价、台账、签证和证据整理 | 形成可核验的量价事实并提交审核 |

其他施工岗位不是本产品的默认操作中心。其成果由岗位成果管理工具或其他系统形成，经适配器转成 Observation/Evidence 后进入造价闭环；必要时保留兼容账号和只读/交接能力，但不继续扩张为独立业务中心。

## 核心闭环

```text
项目/合同基准
  → 图纸与清单版本
  → 工程量与价格事实
  → Engineering Event
  → 变更/签证/计量
  → Evidence + Verification
  → 结算确认
  → Outcome（申报 → 确认 → 结算 → 回款）
  → 项目经理看板与下一行动
```

任何工具接入都必须回答五个问题：属于哪个项目和工程事件、来源与版本是什么、产生了什么观察、由谁核验、是否会改变金额事实。缺一项只进入待核验区，不自动成为事实。

## 工具接入契约

### CAD 工程量计算

CAD 工具负责读图与算量，BuildCostIQ 只接收结果包：`project_id`、图纸版本、WBS/位置、清单编码、数量、单位、计算规则、来源文件哈希、结果版本和核验状态。原始 CAD 与计算过程留在工具侧或本地来源库，确认后的数量再进入造价事实。

### 工程施工项目岗位成果管理

岗位成果工具负责生产、技术、质量、测量等岗位的过程成果。接入时只投影与造价有关的事件、证据、完成量、验收状态和交接结论，不把其人员、表单、流程和权限复制进造价 Core。

### 未来工具

统一走 Adapter/Connector，不直接依赖 Core，不越过人工确认，不替换已确认来源，不创建第二项目账或第二金额账。
