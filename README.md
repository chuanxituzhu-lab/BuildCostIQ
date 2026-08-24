# BuildCostIQ

## P09 当前能力边界
P09“全过程成果经营管理”已作为只读派生能力接入。P01–P08 继续保存合同、清单、图纸、基线、成本、变更、证据和结算专业事实；P09 只读取工程事件的 Outcome 快照，计算成果漏斗、六段价值泄漏和异常经营队列，不新增第二金额事实源。

BuildCostIQ version `v0.8.0-rc8` is a local-first construction-cost foundation and P01–P09 project workbench. P01–P08 own professional facts and P09 is a read-only outcome-management projection over the Core Engineering Event Kernel. Local project facts are distilled first, pasted text is distilled second, and fusion preserves provenance, conflicts, claims, and uncertainty. The WebUI keeps the existing local-first intake, recognition, archive, and provenance controls.

## Quick verification

```bash
python scripts/verify_release.py
```

版本号只维护 `pyproject.toml` 一处；运行时健康接口和 WebUI 会自动读取当前版本。发布新版本时执行：

```powershell
python scripts/bump_version.py --patch
# 或指定版本
python scripts/bump_version.py 0.8.0-rc5
```

重启 WebUI 后，`/api/health`、架构信息和首页版本号会同步更新；CI/临时发布也可使用 `BUILDCOSTIQ_VERSION` 环境变量覆盖显示版本。

## Local WebUI

Install the project in the existing virtual environment, then start the local review workbench:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m gui --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787/`. The WebUI provides the existing project workbench plus P09 outcome management, and uses the P01–P09 gateway while keeping all data local by default. External OCR requires explicit per-file consent. After installation, `buildcostiq-web --port 8787` is an equivalent launcher. See [docs/WEBUI.md](docs/WEBUI.md) for the API boundary.

The homepage shows the current release version, release highlights, and a role operation manual. The workbench now exposes one direct screen for each capability: P01 contract and procurement basis, P02 BOQ intake, P03 drawing register, P04 zero ledger, P05 cost planning, P06 change management, P07 evidence linkage, and P08 settlement review, plus the cross-stage Core 工程事件内核 screen. P01 and P03–P08 provide dedicated multi-file material-intake entries, while P02 provides the dedicated BOQ intake; each entry writes to its own logical project archive area before business records are confirmed. The independent external-basis library stores policy, quota/pricing basis, price information, market prices, and interface snapshots with local source paths and version metadata; P04, P05, and P08 can reference immutable local snapshots. Project exports now open a second-level local export workspace where users choose the export type, filename, and target folder before writing the file, with browser-download fallback. 项目经理或经项目经理授权的行政人员可在人员管理中只录入姓名和岗位，系统为当前项目生成初始登录密码，人员随后使用姓名/登录名登录对应岗位工作台；每个项目拥有独立人员名册，移除一个项目成员不会删除其账号或其他项目成果；更换姓名仍保留原账号、成果和审计链。 It provides role-aware dashboards, local baseline comparison, automated alerts, file viewing, permission-gated edits and soft deletes, multi-file project intake, local recognition, and explicit external OCR consent.

## 部署与存储适配层

默认模式仍是单机本地优先。项目部多台电脑使用时，应只在一台中央服务器运行 WebUI/API，其他电脑通过浏览器访问该服务；不要让多台电脑直接打开或修改共享盘里的项目 JSON 文件。设置中央数据根目录后，部署适配层会统一生成 `projects/`、`sources/`、`archive/`、`basis/`、`auth/`、`backups/` 和 `locks/`，并对同一项目启用跨线程/跨进程写入锁和项目 revision。

中央部署示例：

```powershell
buildcostiq-web --deployment-mode central --node-id project-server-01 --host 0.0.0.0 --port 8787 --data-root D:\BuildCostIQData --backup-root E:\BuildCostIQBackups
```

岗位电脑只打开 `http://项目服务器地址:8787/`。`GET /api/deployment` 可查看节点模式、数据权威归属和一致性策略；绝对物理路径不通过该接口公开。GitHub 只保存代码和文档，项目运行数据留在中央数据根目录，备份目录不作为实时数据库。完整部署步骤见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## Boundaries

- Core owns immutable domain records, provenance hashing, runtime, and the capability gateway.
- Plugins implement P01 contract, P02 bill of quantities, P03 drawings, P04 baseline ledger, P05 cost planning, P06 changes, P07 evidence, and P08 settlement review.
- Adapters handle external storage or future integrations without changing Core.
- Source recognition is local-first: PDF/Office/text/CAD metadata are processed locally and retained as derived Markdown; external OCR is a consent-gated adapter and never runs from upload automatically.
- Project sources and external basis are separate local stores: P01–P08 write to logical project archive areas, while policy, pricing-basis, price-information, market-price, and interface snapshots are versioned in the independent basis catalog and referenced by P04/P05/P08.
- P01–P08 are real implementations; each is executed through the frozen CapabilityGateway and persisted by the adapter-owned project workspace.
- `plugins/normalize.py` and `plugins/basis.py` are shared helper modules, not capabilities.
- P10 and later capability expansion are rejected by the gateway in this release; P09 is the controlled read-only outcome projection.
- The Engineering Event Kernel is a Core domain model, not a ninth capability: it links P01–P08 facts through a permanent event id, append-only status history, baseline impact, production/technical/commercial tracks, three-evidence checks, settlement lifecycle, and local rule alerts.

The included demo uses sanitized identifiers and contains no real project data.

新手学习路径见 [docs/BEGINNER_GUIDE_FEYNMAN.md](docs/BEGINNER_GUIDE_FEYNMAN.md)，按“讲人话 → 动手做 → 自己复述 → 找漏洞”完成从项目建档到 P09 成果经营的完整练习。

单个市政项目闭环验收见 [docs/MUNICIPAL_WORKFLOW_ACCEPTANCE.md](docs/MUNICIPAL_WORKFLOW_ACCEPTANCE.md)。在本地运行 `python scripts/verify_municipal_workflow.py`，可重复验证 P01–P09、五类黄金场景、三线人工确认、协同动作、三层验收、数量/材料链和数字资产哈希是否全部闭合。

## 全过程项目管理融合

“全过程项目管理概要”已按负熵原则融合为 P09 成果经营能力：不复制合同/清单/成本/计量/结算/回款金额。每个 Event 现在有独立的 `Outcome` 双状态机、可追加的快照修订、六段 Value Leak 派生和只显示异常的经营队列。造价经理可在事件卡片追加成果快照，P09 与经营看板可沿“实体 → 证据 → 申报 → 确认 → 结算 → 回款”查看价值转化。完整规则和边界见 [docs/PROJECT_MANAGEMENT_DISTILLED.md](docs/PROJECT_MANAGEMENT_DISTILLED.md)。

分包管理采用双责任线工作流：技术负责人负责“拆包 → 审方案 → 交底 → 技术放行 → 验收移交”，生产经理负责“接放行 → 排产配资源 → 跟踪实物量 → 纠偏 → 量验移交”。两条线共用现有 Core Event、Evidence、Verification、Outcome 和协同任务，不新增第二金额事实源。

造价核心责任链固定为：项目经理负责决策、资源和升级；技术负责人负责技术边界、方案与放行；生产经理负责计划、资源和现场兑现；施工/测量/质量/试验形成可核验事实；造价员形成量价基础；造价经理负责商业总审、计量、变更、结算初审与 Outcome。项目经理不能代改专业事实，任何跨线冲突回到 `Event → Evidence → Verification → Outcome`，由对应责任线负责人确认。岗位输入、输出、下一接收人和不可修改项由 `/api/line-contracts` 的 `role_flows` 发布，WebUI 只显示当前岗位相关交接。
