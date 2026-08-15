# Changelog

Project: BuildCostIQ

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
