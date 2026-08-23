# Changelog

## v0.8.0-rc5 - 2026-08-21

- Version metadata refreshed by scripts/bump_version.py.
- 清理正式本地名册：归档 456 条历史/测试账号，保留 14 个基础岗位账号。
- 人员关系按项目独立维护；当前项目默认显示 14 个基础岗位，新项目不会继承其他项目新增人员。
- 项目内移除人员只解除当前项目成员关系，不删除全局登录账号或其他项目成果。
- 首页新增 v0.8.0-rc5 岗位操作手册：按“输入 → 操作 → 成果 → 复核”展示各岗位的最小执行闭环，并同步项目经理/授权行政人员的新增人员说明。
- 优化人员管理的新增人员表单：姓名/登录名采用较窄输入框，岗位角色字段左移并限制在当前面板内，避免长岗位名称造成横向溢出。
- 生产经理和技术负责人新增专属分包双线工作流：技术线负责拆包、方案、交底、放行与技术移交；生产线负责接放行、排产、实物量、纠偏与量验移交，统一使用现有协同和证据链。
- 固化“造价核心责任链”：项目经理负责决策/资源/升级，技术负责人负责技术边界/放行，生产经理负责计划/资源/兑现，造价员形成量价基础，造价经理负责商业总审与 Outcome；新增角色级输入、输出、下一接收人、升级对象和不可修改项契约，WebUI 按当前岗位显示交接卡片。
- 新增部署与存储适配层：支持 single-node/central/edge 节点模式、统一数据根目录、项目级跨线程/跨进程写入锁、revision 一致性标记、备份根目录和 `GET /api/deployment` 状态接口；不允许终端直接把共享文件夹当实时数据库。
- 新增岗位专属成果工作面：仓管、施工、测量、试验等岗位按各自输入字段、成果类型和协同对象独立录入；成果仅通过 Event/Evidence/Source/Coordination 互联，交接只发送给契约声明的下一责任岗位，不建立第二金额事实源。

## v0.8.0-rc4 - 2026-08-21

- Version metadata refreshed by scripts/bump_version.py.
- 项目经理或已获项目经理授权的行政人员录入人员时只需填写姓名和岗位；系统自动生成初始登录密码。
- 初始密码只在新增接口响应和当前管理页面返回一次，人员随后使用姓名/登录名与初始密码登录对应岗位工作台；刷新名册后不再返回密码。
- 保留显式密码参数用于本地脚本迁移，新增“无密码录入 → 登录验证”验收测试。
- 人员名册改为按 `project_id` 独立维护：新增、移除、改名、岗位组合和行政授权均只作用于当前项目；移除项目成员不会删除其全局登录账号或其他项目成果。

## v0.8.0-rc3 - 2026-08-21

- Version metadata refreshed by scripts/bump_version.py.
- 全面复核岗位工作面：前后端菜单契约统一，仓管员仅保留总览、P02 物资清单、工程事件、证据和协同；不再显示 P04 零号台账。
- 现场、生产、技术、质量、试验、安全、采购和行政岗位移除跨岗位资料检索入口；资料员保留归档检索，造价/项目管理岗位保留经营检索。
- `/api/search` 与岗位菜单使用同一角色边界，服务端拒绝非授权岗位的检索请求；新增前后端菜单一致性和仓管员越权测试。

## v0.8.0-rc2 - 2026-08-21

- Version metadata refreshed by scripts/bump_version.py.
- 收口 P09 全过程成果经营：仅以现有 P01–P08 与 Core Event/Outcome 事实生成漏斗、六段价值泄漏和异常经营队列；P09 不提供金额录入，也不建立第二金额事实源。
- P04 零号台账录入权限收紧为造价经理、造价员；其他岗位仅能通过自身工作面引用派生结果，服务端同时拒绝越权写入。
- 三条责任线改为策略自动归属：生产线→生产经理、技术线→技术负责人、造价线→造价经理；只有对应主管负责人可以确认或修改责任线映射。
- 岗位 WebUI 与上述边界同步收口，P09 仅对项目经理和造价经理开放，责任线预览保留但非主管账号不可确认。

Project: BuildCostIQ

## Unreleased — 全过程项目管理负熵化融合

- Added P09 全过程成果经营管理 as a read-only Gateway capability over the Core Event Kernel; P01–P08 remain the only professional fact owners.
- Added `GET /api/p09`, a dedicated P09 WebUI screen, and Gateway/runtime/health registration for the derived outcome projection.

- Distilled the “全过程项目管理概要” into P09 and the existing Core Event Kernel without adding a second amount ledger.
- Added an independent append-only Outcome state machine inside each Event, five minimal Outcome types, snapshot revisions, and rejection/abandonment reasons.
- Added derived six-stage Value Leak calculation and a role-safe outcome vector; existing P01–P08 records remain the only professional amount sources.
- Added `POST /api/event-kernel/outcome`, dashboard outcome funnel/value-leak/abnormal queue data, and造价经理-only Outcome snapshot controls in the WebUI.
- Documented the distilled constitution, boundaries, golden scenarios, and negative-entropy rules in `docs/PROJECT_MANAGEMENT_DISTILLED.md`.
- Added the current municipal personnel role catalog (production, technical, cost, quality, safety, procurement, warehouse, document and administrative roles) without expanding Core or adding P10.
- Changed personnel governance to project-manager direct control with explicit project-manager delegation to administrative officers; added authorize/revoke, delete, live session rehydration and audit endpoints.
- Added a recoverable local registry reset script and seeded one basic account per current role after archiving the previous active registry.
- Added personnel handover: project managers or authorized administrative officers can rename a person without creating a new account; `user_id`, password, role, audit and project work remain continuous, while the old name is retained in history.
- Added configurable field-role assignment so `surveyor` and `site_engineer` can remain separate or be merged on one account per project needs, without duplicating work products.
- Added role-specific WebUI workbenches distilled from the municipal project workflow: each role sees only its authorized work surfaces and a five-part “我的工作 / 待交成果 / 审核状态 / 异常退回 / 直接责任链” home view.
- Added server-side role-scoped workspace projections (`visible_views`) and capability write guards for P01–P08, so hiding a tab is never the only permission boundary.
- Restricted the reinforced management dashboard to project managers, cost managers, and production managers; ordinary professional roles remain on their own execution workbench.
- Renamed the field workbench label from `施工员/现场工程师` to `施工员/测量员` while retaining legacy role aliases for existing accounts.
- Added concise role-specific execution loops and completion guidance to each professional workbench; merged field accounts show the union of施工员 and测量员 outputs without duplicating facts.

## v0.8.0-rc1 - 2026-08-17

- Added the Core Engineering Event Kernel v1.0 without expanding the frozen P01–P08 CapabilityGateway boundary.
- Added deterministic local-first distillation of project sources and saved P01–P08 records, followed by conservative text distillation and provenance-preserving fusion.
- Added permanent `EV-YYYY-NNNN` event ids, append-only status history, twelve-domain event records, state-transition guards, state vectors, three-evidence consistency checks, and local risk rules.
- Added the WebUI “工程事件内核” work surface with local/text/fused fact counts, conflict and claim visibility, event intake, status progression, state vectors, audit-ready checks, and role-aware cost redaction.
- Added `/api/event-kernel` read, distill, create, transition, and cross-check endpoints; all event distillation remains local and reports `external_sent: false`.
- Kept the existing multi-file local-first intake, P01–P08 lists, external-basis catalog, search, permissions, and audit trail unchanged.

## v0.7.2-rc15 - 2026-08-15

- Decoupled local file saving from recognition for WebUI intake: files are quickly written to their local category folders first, while local recognition runs in the background and updates the visible result.
- Multi-file intake keeps the selected-file order and reports each local save before background recognition updates the result.
- P01-P08 material lists default to the newest two visible files and expose the remaining files through a three-dot expand/collapse control.
- Source actions are grouped under a per-file second-level “⋯ 操作” menu for viewing, path copying, recognition, metadata edits, and permission-gated soft deletion.

## v0.7.2-rc14 - 2026-08-15

- Compact project-library view now keeps the newest two materials visible, matching the full list order.

## v0.7.2-rc13 - 2026-08-15

- Project library defaults to two visible materials and provides an explicit expand/collapse control for the remaining files.
- Search and clear actions return the library to the compact two-item view; stage-specific P01-P08 working lists remain unchanged.

## v0.7.2-rc12 — 2026-08-15

- Added independent logical archive subfolders for P01 contract/procurement classifications: 招标阶段、投标阶段、定标阶段、合同阶段 and 执行解释.
- Added read-only local category archive copies under `runtime/archive/<project>/...`; the category folder path is shown separately from the immutable original path.
- The P01 page now shows the selected category’s full archive location before upload and each uploaded file’s category-specific path after upload.
- Normalized legacy source metadata so existing classified files display under the correct category folder; removed duplicate stage names such as 图纸资料资料.
- Kept the immutable content-addressed original store and frozen Core/CapabilityGateway P01–P08 boundary unchanged.

## v0.7.2-rc11 — 2026-08-15

- Fixed multi-file intake feedback across project files, P01–P08 material entries, and the external basis library.
- BOQ uploads now return their saved source metadata, archive location, and local original path to the WebUI.
- Added immediate “正在保存” feedback, per-file completion results, and visible logical archive locations before and after upload.
- External basis intake now supports multiple files and reports each file’s local save path while preserving the existing metadata and consent boundaries.

## v0.7.2-rc10 — 2026-08-14

- Added a global “资料与问题” search entry and dedicated WebUI workspace for project materials, external basis snapshots, and saved P01–P08 records.
- Added local evidence-grounded question summaries with visible source, archive path, recognition status, and uncertainty labels.
- Defaulted search and question answering to local-only evidence; external AI remains disabled and requires explicit consent at a future adapter boundary.
- Added strict long-question matching and role-aware result visibility so unsupported questions do not become false positive answers.

## v0.7.2-rc9 — 2026-08-14

- Fixed inline viewing for Unicode-named source files by emitting an ASCII fallback and UTF-8 filename response header.
- Added regression coverage for opening a Chinese-named source through the WebUI endpoint.

## v0.7.2-rc8 — 2026-08-14

- Added project-material search by filename, archive category, recognition category, and local path; filtered results retain the existing 查看 action for opening the source file.
- Grouped relevant classification dropdowns so the most-used and recently used three-to-five choices appear first while the complete category set remains available.
- Updated the WebUI release banner and runtime metadata without changing the frozen Core/CapabilityGateway P01–P08 boundary.

## v0.7.2-rc7 — 2026-08-14

- Renamed P01 in the user-facing workbench to 合同与招采依据 and added five intake classifications: 招标、投标、定标、合同 and 执行解释。
- Added logical archive locations for the overview and P01–P08 material-intake entries; source cards now show the archive location and local original path.
- Added an independent local 外部依据库 for policies, quotas/pricing basis, price information, market prices, and interface snapshots.
- Added version-aware basis metadata and P04/P05/P08 project-reference entry points; raw hashes and backend IDs remain hidden from the normal UI.
- Kept the frozen Core/CapabilityGateway boundary and default local-only data policy unchanged.

## v0.7.2-rc6 — 2026-08-14

- Changed project export buttons to open a second-level local export workspace instead of downloading immediately.
- Added export type selection, editable filenames, folder selection through the browser File System Access API, explicit confirmation, and a default-download fallback.
- Kept export authorization and the Core/CapabilityGateway boundary unchanged.

## v0.7.2-rc5 — 2026-08-14

- Added dedicated multi-file material-intake entries to P05 cost planning and P08 settlement review, completing the P01–P08 intake coverage.
- Kept the existing P02 BOQ intake and reused the local archive, recognition reports, paths, view actions, and audit-controlled lifecycle across all stages.

## v0.7.2-rc4 — 2026-08-14

- Added dedicated multi-file material-intake entries to P03 drawings, P04 zero ledger, P06 changes, and P07 evidence linkage.
- Reused the local source archive, recognition reports, storage-path display, view actions, and permission-gated soft deletion across these workspaces.
- Kept the business forms and frozen Core/CapabilityGateway boundary unchanged.

## v0.7.2-rc3 — 2026-08-14

- Added a dedicated P01 contract-material intake entry with multi-file selection.
- Reused the local source archive and recognition flow so contract originals, storage paths, recognition status, and derived artifacts remain viewable in the contract workspace.
- Kept contract master data confirmation separate from file intake; Core and the CapabilityGateway remain unchanged.

## v0.7.2-rc2 — 2026-08-14

- Fixed the left-side P01–P08 work-assist entries so they navigate to the same workbench views as the top menu.
- Added delegated navigation handling for dynamically refreshed work-assist items.

## v0.7.2-rc1 — 2026-08-14

- Added a permission-gated personnel management backend entry for project managers and cost managers.
- Added local personnel snapshots without password material and a separate personnel audit trail for account creation.
- Added the WebUI personnel management tab, role summary table, local-only account entry, and estimator-level hiding/403 enforcement.
- Updated release metadata and homepage highlights for the personnel-management iteration.

## v0.7.1-rc1 — 2026-08-14

- Added three role scopes: project manager KPI-only view, cost manager full permissions, and cost estimator operational access at level two.
- Added API-level authorization for workspace, P01–P08 operations, exports, source actions, and settlement review.
- Added cost-detail redaction for estimator responses and KPI-only workspace/dashboard responses for project managers.
- Updated the WebUI registration, navigation, cost-plan inputs, review gate, project-control policy, and export actions to match the three roles.

## v0.7.0-rc1 — 2026-08-14

- Implemented all eight frozen capabilities as usable Gateway-backed workbench stages.
- Added P01 contract register, P03 drawing register, P04 zero ledger, P06 change register, and P07 evidence linkage with local persistence and audit events.
- Added direct WebUI tabs and editable tables for P01–P08, plus a project overview coverage panel and assistant links.
- Extended the local dashboard with contract completeness, drawing review, pending-change, evidence-verification, and zero-ledger alerts.
- Kept Core and the P01–P08 boundary frozen; external CAD, Office, and OCR integrations remain adapter boundaries.

## v0.6.0-rc1 — 2026-08-13

- Added a role-aware project intelligence dashboard for project managers and cost/estimating staff.
- Added local baseline comparison, cost-over-limit alerts, pending-pricing alerts, review cadence alerts, and repeated-issue summaries.
- Added local review snapshots so the dashboard can show near-7-day and near-30-day issue counts without sending project data externally.

## v0.5.1-rc1 — 2026-08-13

- Added the absolute local storage path for every original source file to the project library metadata and intake result.
- Added the local storage path for generated Markdown recognition copies.
- Added visible path notes and a copy-path action in the file interface; legacy project sources are backfilled when their workspace is opened.

## v0.5.0-rc1 — 2026-08-13

- Added a view action for every project source and a local recognition-derivative view when available.
- Added local registration and login with separate project-manager and cost-estimator workbench roles.
- Added permission levels: source metadata and business edits are auditable; source deletion is a project-manager-only soft delete that preserves original bytes and the audit trail.
- Added project-manager control view with permission policy, audit events, and risk-color legend.
- Added red urgent-blocker, yellow warning, and blue notice presentation for workflow findings.
- Added release highlights to the homepage and versioned release metadata for the v0.5.0-rc1 GitHub tag.

## v0.4.0-rc1 — 2026-08-13

- Extended the workbench intake control to accept multiple files in one selection, including PDF, Word, PowerPoint, images, CAD, Excel, CSV, and project documents.
- Added project setup intake for initial project information files; uploaded photos, Word, Excel, PDF, and related materials are saved to the local project and automatically recognized/classified.
- Added per-file intake feedback so users can see whether a file was converted locally, recognized, needs OCR, or is currently unsupported.
- Added local-first PDF/Office/text/CAD recognition and Markdown archive derivatives while preserving the original source file.
- Kept external OCR behind explicit per-file consent; no external transfer occurs during upload or local recognition.
- Updated the homepage to display the active version and release highlights.

## Unreleased

- Implemented P08 (settlement / BOQ review) as a real capability, replacing the
  declarative placeholder. Deterministic rule engine only — arithmetic and
  consistency defects (合价校验, 编码格式与重复, 工程量, 单位错配, 单价偏离,
  漏项覆盖) are decided by rules, not by a model. Every finding carries a
  `rule_id` and an `evidence` basis and records as
  Evidence(kind="review_finding"). Severities are block/warn/info; a single
  `block` sets `publishable=False`. All reference inputs (unit catalogue, price
  book, quantity ceilings, expected divisions) are injected — nothing is
  assumed, and a rule that has no reference simply does not fire.
- Added `plugins/basis.py`: price-basis (口径) governance. A unit price is only
  meaningful under a declared 税制 / 价格类型 / 出处 / 取价期. `comparable()`
  distinguishes *undeclared* from *conflicted* and refuses the subtraction in
  the latter case.
- Added `plugins/normalize.py`: unit normalisation (㎡/m²/平方米 → m2) and
  quota-multiplier conversion (100m3 → m3 = ×100), with cross-dimension pairs
  refused rather than silently computed.
- **Fix (P05):** the market-vs-contract variance was computed without any check
  that the two price books share a tax basis. Subtracting a 含税 market price
  from a 除税 contract price is arithmetically valid and 造价-wise wrong, and it
  failed silently. `cost_control` now reports `comparability` and returns no
  variance number when the declared bases conflict. External totals are
  unchanged; undeclared bases stay backward-compatible.
- **Fix (P02):** `parse_standard_boq` assumed `rows[0]` was the header. Real
  清单 exports put 工程名称/标段/编制单位 banner rows above the table, so the
  parser failed on the most common input shape. `find_header_row` now locates
  the header by alias-hit scoring over the first 12 rows.
- Added `tests/test_review.py` (28 tests) and `examples/review_workflow.py`.

- Implemented P05 (cost planning) as a real capability. Prices P02's BOQ items
  against the winning-bid (中标) unit price as the authoritative basis; items
  absent from the contract price book are flagged `re-priced-pending` with a
  null price and zero amount — never guessed. The external summary keeps the
  contract subtotal and the pending items strictly separate. An optional market
  price book feeds an isolated `cost_control` variance (contract − market) that
  can never enter any external total. Currency maths use Decimal (half-up).
  Records as Evidence(kind="cost_plan_item"). Core and the frozen boundary
  unchanged.
- Added `examples/contract_prices.sample.json` and `examples/market_prices.sample.json`.

- Implemented P02 (bill-of-quantities) as a real capability: parses GB 50500
  standard BOQ tables and, in merge mode, consolidates 广联达-style per-component
  quantity sheets via a JSON mapping table. Output rows carry the five clause
  elements (code/name/feature/unit/quantity) and record directly as
  Evidence(kind="boq_item"). Pure openpyxl parsing — no Excel process, no
  pickle, no GUI. Core, gateway, and the frozen P01–P08 boundary are unchanged.
- Added `openpyxl>=3.1` dependency and `examples/boq_mapping.sample.json`.

## v0.3.0-rc1

- Added frozen Core runtime and capability gateway.
- Added P01–P08 plugin contracts and default implementations.
- Added immutable source storage, evidence provenance, tests, CI, Docker, and sanitized demo workflow.
