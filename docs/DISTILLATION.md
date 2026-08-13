# 蒸馏溯源记录（Distillation Provenance）

本文件记录外部项目的扫描、取舍与改造过程。原则：**不直接复制外部代码**；
先穿透到底层问题，再抽取核心逻辑，最后按本项目的既有约定重写。

## 扫描范围

GitHub 关键词：工程造价 / 工程量清单 / 定额计价 / 广联达 / construction cost
estimation / BIM quantity takeoff / IFC quantity。中文造价类项目总量很小
（"造价 清单" 全站仅 5 个仓库），且多为个人早期作品；国际项目量大但基于
CSI/Uniformat 体系，与 GB 50500 编码体系不通。

## 采纳

| 来源 | 许可 | 提取的底层判断 | 落地位置 |
|---|---|---|---|
| BruceLee1024/cost-data · `governance.py` | MIT | 价格口径不清 → 只展示原始价、不进入可比统计。**价格不是一个数，是"某口径下的数"** | `plugins/basis.py` |
| BruceLee1024/cost-data · `normalization.py` / `unit_conversion.py` | MIT | 单位写法脏 + 定额单位带倍率 → 不归一就比价会产生静默百倍误差 | `plugins/normalize.py` |
| BruceLee1024/cost-data · `quality.py` | MIT | 有 error 则 `publishable=False` —— 质量结论要有闸门，不能只是提示 | `review_boq()` 的 `publishable` |
| MBSOFTCOM/cost-review · `rule_engine.py` | 未声明 | 初审的大部分是算术与一致性问题，可用确定性规则定死，不必动模型；每条发现带"判定依据" | `plugins/review.py`（重写） |
| MBSOFTCOM/cost-review · `excel_parser.py` | 未声明 | 表头不在第一行 → 扫描前 N 行按关键词命中打分定位 | `plugins/boq.find_header_row`（重写） |
| lufeng6542/gb-construction-quota | MIT | 清单编码 → 名称 / 计量单位 / 必描述项目特征 的结构化目录，可支撑单位校验与特征完整性校验 | 以 `reference_units` 注入接口对接，**数据不内置** |

## 改造要点（为什么不是照搬）

* **金额一律 Decimal。** cost-review 的合价校验用 float —— 用浮点去证明
  "这个数不对"本身就不成立。与本项目 P05 既有口径统一。
* **删除 `qty > 100_000` 魔数。** 与单位无关的固定阈值，对市政道路（延米
  十万级）刷屏误报，对精装（个/套）又抓不住。改为按单位注入上限。
* **删除硬编码分部模板。** cost-review 内置 civil/install 两套，市政 04 章
  不在其中。改由调用方按项目类型传入。
* **删除字符集 Jaccard 匹配。** `set(名称)` 求交并比忽略字序与字频，
  "钢筋混凝土管" 与 "混凝土钢管" 会得高分；把价格偏离结论建在这种匹配上是
  危险的。本实现只在调用方给出明确 `code → 参考价` 时才判偏离。
* **口径判定从"警告"升级为"闸门"。** cost-data 只输出警告字符串，采信与否
  交给调用方 —— 警告会被忽略，拿不到数不会。`comparable()` 在税制冲突时
  直接不返回偏差数。
* **剥离 Session 依赖。** cost-data 的归一函数要查数据库才能拿规则。归一是
  纯计算，不该依赖持久层；自定义规则改为 `extra` 参数注入。
* **严重度改为 block/warn/info。** red/yellow/blue 是展示层概念，而本项目
  边界规定 capability 只出结构化结果、不管展示。

## 明确拒绝

* **datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR**（55,719 工作项
  数据库）—— 许可为 **CC BY-NC 4.0 + 商业授权**。本项目为 MIT，任何商业用途
  下都不能内置该数据集。且其工作项体系基于国际分类，与 GB 50500 编码不通，
  用于中国市政场景需整体重做映射。其"工作项 → 资源（人材机）分解"的结构
  思路可供 P05 组价参考，但**数据与代码均不引入**。
* **nainai23012/chengqingdan_v2（诚清单）** —— P02 已在上一轮蒸馏过其匹配合并
  逻辑（xlwings→openpyxl、pickle→JSON、去 Qt），本轮无新增可提取项。
* **cost-review 的 SaaS 外壳**（auth / billing / admin / Next.js 前端）与
  **cost-data 的持久层**（SQLAlchemy 模型、Alembic 迁移、定点数存储）——
  属于部署与应用层关切，与本项目"Core 冻结 + 能力网关"的边界不兼容，不引入。
* **cost-data 的 `fixedpoint.py`（int64 定标存储）** —— 是数据库落盘方案。
  本项目当前无写库路径，Decimal 已足够；引入会平白增加复杂度。待 P04/P07
  真正落库时再评估。

## 未内置第三方数据的理由

`reference_units`（编码 → 规范计量单位）、`reference_prices`、
`expected_divisions` 全部作为**注入参数**，不在仓库里内置任何一份定额或清单
目录。原因有三：一是各地定额与清单目录版本各异（GB/T 50856-2024 与 GB 50500
体系、重庆 2018 定额、天津 2025 规范并存），内置任何一份都会误导；二是规避
第三方数据的许可与准确性责任；三是保持 Core 与 plugins 的纯计算属性 ——
事实由调用方提供，规则由本项目提供。
