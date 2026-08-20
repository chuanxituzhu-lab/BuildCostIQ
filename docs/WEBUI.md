# Local WebUI

## P09 outcome management
The WebUI includes a dedicated P09 成果经营 screen for 项目经理 and 造价经理. It calls the read-only P09 projection, showing the Event → Evidence → Outcome funnel, six value-leak stages, daily exception queue, and boundary rules. P09 derives from existing P01–P08/Core Event facts and never creates a second amount ledger or an amount-entry form.

新手按步骤学习请参阅 [BEGINNER_GUIDE_FEYNMAN.md](BEGINNER_GUIDE_FEYNMAN.md)。每一步都包含操作动作、费曼式复述问题、完成标志和常见错误。

BuildCostIQ includes a local WebUI business workbench for all implemented P01–P09 capabilities. P01–P08 own professional facts and P09 is a read-only derived outcome-management projection. It runs on the same controlled Core gateway and does not add a second database.

### Permission and responsibility-line boundary

- P04 零号台账的录入/修改只允许 `cost_manager`（造价经理）和 `cost_estimator`（造价员）；其他岗位不显示 P04 工作面，服务端也拒绝 `/api/baseline` 越权写入。
- 生产线、技术线、造价线由策略自动归属到生产经理、技术负责人、造价经理。预览可供其他岗位查看，但只有对应主管负责人可以确认或修改映射；确认后的数据才会写回 Core/P01–P08/Outcome。
- P09 经营结果只读，只有项目经理和造价经理可以进入；任何岗位都不能通过 P09 直接录入金额。

## Start

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m gui --host 127.0.0.1 --port 8787
```

After `pip install -e .`, the console entry point is also available:

```powershell
buildcostiq-web --port 8787
```

Open `http://127.0.0.1:8787/`. The workbench starts at a project overview, saves a local project workspace, and provides a project file library for Excel, Word, PDF, CAD, image, and other source files. Every uploaded source is stored locally first and sent through local recognition when a local extractor is available. The recognizer creates a category, tags, confidence, text preview, and a Markdown derivative while preserving the original bytes. Scanned PDFs and images are marked as needing OCR when local extraction finds no text. The BOQ step provides Excel/CSV intake or a user-facing table. Continue the checked items into contract-based cost planning, then send the priced rows into settlement review. The left-side work assistant shows the next action and outstanding items. The overview also contains an exchange center: Excel/CSV and Word-compatible paths are direct, while CAD and budget-software files are shared through the portable project exchange package. The UI only assembles capability context; business decisions remain in the Gateway path.

The `v0.8.0-rc1` intake flow accepts multiple files in one selection. WebUI uploads first write the originals into their local category folders, then local recognition runs in the background so the save result is not blocked by document conversion; the UI reports the save location immediately and updates recognition status afterward. Every project-material entry and the external basis entry shows the logical archive location, the actual local original path, and the classification-folder path for each file. The project overview and every P01–P08 material list keep the newest two materials visible by default and reveal the remaining files through a three-dot expand/collapse control. Each source has a second-level “⋯ 操作” menu for viewing the original or recognition copy, copying paths, local recognition, metadata edits, and permission-gated soft deletion. Project sources also receive read-only local category copies under `runtime/archive/<project>/...`, with that physical folder path shown separately. P01 contract/procurement uploads use independent logical subfolders for 招标阶段、投标阶段、定标阶段、合同阶段 and 执行解释; existing classified metadata is normalized when the project workspace is loaded. In the BOQ step, table files are sent through P02 and combined when several tables are selected; PDF, Word, PowerPoint, image, CAD, and article files are saved to the project library and reported individually. The header now provides a global “查资料或问问题” entry and the workspace navigation provides “资料与问题”. Search covers local project sources, local recognition Markdown, external-basis snapshots, and saved P01–P08 records. The question mode returns only a local evidence summary with source name, archive path, recognition state, uncertainty labels, and an explicit “no sufficient evidence” outcome; external AI is not called and any future provider must remain behind explicit consent. The project overview continues to provide a project-material search by filename, category, or local path; each result keeps the existing 查看 action so the original file can be opened, including Unicode-named files. P03–P08 each have a dedicated material-intake entry with its own logical archive area, while P02 retains its dedicated BOQ intake. Project exports open a second-level export workspace for selecting content, filename, and a local target folder through the browser File System Access API; “下载到默认位置” remains available when folder authorization is unavailable. The project overview has a separate “接入初步资料” entry for initial project information, which uses the same local-first archive and recognition flow.

The v0.8.0-rc1 Core “工程事件内核” screen is a cross-stage work surface, not a new P09 capability. It first summarizes local sources and saved P01–P08 records into traceable facts, then conservatively distills text into event type, origin, dimensions, amounts, dates, locations, and unverified claims. The fusion panel shows local/text/fused counts, conflicts, source references, and claims; local structured facts win on same-field conflicts but the text fact remains visible for review. A user can apply the suggested event to a visible draft and save a permanent `EV-YYYY-NNNN` event. Each event displays the state vector (`Event`, `Production`, `Technical`, `Commercial`, `Evidence`, `Approval`, `Measurement`, `Audit`, `Cash`, `Risk`), guarded next-state actions, three-evidence checks, and local warnings. Event status transitions remain append-only and every write is audited; cost details remain redacted for cost estimators and project managers receive indicator-only event cards. The process never calls an external AI provider and returns `external_sent: false`.

The 外部依据库 is independent from the project file library. It stores 政策法规、定额与计价依据、造价信息、市场价格 and 外部接口快照 with source organization, source address, publication date, effective period, applicable region, tax/pricing basis, version, and local storage path. P04 零号台账、P05 成本计划 and P08 结算初审 each provide a “选择计价依据” entry. Referencing a basis stores a point-in-time snapshot in the local project workspace, so later updates cannot silently rewrite historical project conclusions. Hashes, backend identifiers, raw context, and recognition payloads remain hidden from the normal user interface.

## P01–P08 workbench

The workspace exposes a direct screen for every frozen capability:

- P01 合同与招采依据台 — contract/procurement file classes, contract master data, dates, amount, and obligations.
- P02 清单资料 — BOQ file/table intake and normalization.
- P03 图纸登记台 — drawing number, discipline, revision, status, and source.
- P04 零号台账 — baseline entries, amount calculation, basis, and source.
- P05 成本计划 — contract and market price books with isolated comparison.
- P06 变更工作台 — change reason, amount impact, owner, status, and decision queue.
- P07 证据关联台 — source-to-record links with verification state.
- P08 结算初审 — deterministic settlement and publication gate.

Each structured stage calls its matching capability through `Runtime.gateway`, persists the result under the local project workspace, and appends an audit event when a logged-in user saves it. The dashboard aggregates the stage summaries but does not replace the individual work surfaces.

The “经营看板” is role-aware. Project managers see important project indicators, risk priority, cost-over-limit alerts, and review cadence without line-item details; cost managers see all baseline comparison rows and cost details; cost estimators see the operational issue queue and protected cost fields. P05 contract-vs-market comparison remains isolated from the external cost-plan total. Default local alert lines are 3% for yellow warning and 10% for red critical over-limit; these are presentation thresholds and can be made project-configurable later. Each P08 run stores a local review snapshot, allowing near-7-day and near-30-day issue counts and repeated-rule summaries without external transfer.

### Role workbench boundary

The municipal workflow does not present one universal menu. After login the browser projects the assigned role(s) into an independent workbench; the API returns the same `visible_views` scope and removes unrelated stage payloads. The field roles `surveyor` and `site_engineer` may be merged, in which case the two scopes are unioned without sharing account identity with another person.

The field workbench is labelled `施工员/测量员`; existing `现场工程师` aliases remain valid for backwards-compatible login/role migration. Each role home shows only its own outputs, execution loop and completion boundary.

| Role line | Primary WebUI surfaces |
|---|---|
| 项目经理 | 经营看板、工程事件、P09 成果经营、协同、人员治理 |
| 造价经理 | P01–P09、依据库、协同、项目控制 |
| 造价员 | P01/P02/P04/P05/P06/P07、工程事件、依据库、协同（金额脱敏） |
| 技术/生产 | 图纸、变更、事件、证据、协同；生产经理另有进度看板，不直接录入 P04 |
| 施工/测量/质量/试验/安全 | 各自现场成果、图纸/事件/证据和责任链 |
| 资料/采购/仓管 | 各自资料或物资事实、证据和协同关系 |
| 行政人员 | 仅协同；人员管理必须由项目经理授权 |

普通岗位首页固定为“我的工作 → 待交成果 → 审核状态 → 异常/退回 → 直接责任链”。隐藏菜单不是唯一安全措施：P01–P08 写接口还按岗位能力拒绝越权请求。

## v0.5.0-rc1 workflow controls

- Every project source has a `查看` action. The original bytes remain in the immutable local source store; a generated Markdown recognition copy can be opened separately when available.
- Every source entry records the absolute local path of the original file and, when present, its Markdown recognition copy. The interface displays both paths and provides a copy-path action; opening an older workspace backfills missing path metadata from its content hash. Upload and workspace responses expose the same `storage_path` metadata for local integrations.
- The first screen is a local registration/login surface. `项目经理` sees KPI-only overview and dashboard screens plus the personnel-management backend entry; `造价经理` has all P01–P08, source, cost, export, soft-delete and audit permissions; `造价员` can intake, recognize, modify metadata, and edit operational data while sensitive prices and costs are hidden and personnel management is unavailable. Personnel management belongs to the project manager and explicitly authorized administrative officers.
- Source metadata edits, BOQ edits, cost-plan generation, recognition, review runs, views, uploads, and soft deletes append an audit event containing actor, time, target, and relevant details.
- Review findings use red for urgent blockers, yellow for warnings, and blue for notices. The colors are a presentation of the existing rule severity and do not replace evidence.

## API surface

- `GET /api/health` — runtime version and registered P01–P09 capabilities.
- `GET /api/p09?project_id=...` — read-only P09 outcome funnel, value leaks, and abnormal queue; only project manager/cost manager.
- `GET /api/architecture` — the frozen layer map, capability statuses, shared helpers, and invariants used by the UI.
- `GET /api/sample` — sanitized seed data used by the user-facing demo screen.
- `GET /api/connectors` — the external-tool connector catalog and supported directions/formats.
- `GET /api/recognition/catalog` — local recognizers and external providers, including whether explicit consent is required.
- `GET /api/basis` — local external-basis catalog and business metadata; requires `view_basis`.
- `GET /api/basis/view?basis_id=...` — authenticated view of an external-basis original; add `derived=1` for a local Markdown copy.
- `POST /api/auth/register` and `POST /api/auth/login` — local role registration and login; the returned bearer token is held in the browser session.
- `GET /api/auth/me` — current local role and permissions.
- `GET /api/personnel` — personnel list and personnel-management audit trail; requires `manage_personnel`.
- `POST /api/personnel` — locally creates a role account and appends `personnel.created`; requires `manage_personnel`.
- `GET /api/source/view?project_id=...&source_id=...` — authenticated inline view of an original source; add `derived=1` for a Markdown recognition copy.
- `POST /api/source/modify` — authenticated metadata revision; requires `modify_source` and appends an audit event.
- `POST /api/source/delete` — cost-manager-only soft deletion; original bytes remain and the event is auditable.
- `GET /api/audit?project_id=...` — authenticated project audit trail.
- `POST /api/project` — creates or updates a local project workspace.
- `GET /api/workspace?project_id=...` — resumes the saved project state.
- `POST /api/source/upload` — saves a generic project source in the immutable source store and project library.
- `POST /api/basis/upload` — saves a policy, pricing-basis, price-information, market-price, or interface-snapshot file to the independent local basis catalog.
- `POST /api/basis/reference` — stores a versioned local basis snapshot reference for P04, P05, or P08.
- `POST /api/source/recognize` — reruns local recognition or requests an explicitly authorized external recognition call for one source.
- `GET /api/dashboard?project_id=...` — authenticated role-aware baseline, comparison, alert, review-cadence, and weekly/monthly issue summary.
- `GET /api/event-kernel?project_id=...` — Core event state vectors, local rule alerts, catalog values, and the latest role-aware distillation snapshot.
- `POST /api/event-kernel/distill` — distills local project data first, optionally distills supplied text, and stores a local provenance-preserving fusion snapshot; external sending is always false.
- `POST /api/event-kernel/events` — creates a permanent event with the visible Core domains and initial `DISCOVERED` state.
- `POST /api/event-kernel/transition` — applies the Core state guards and appends immutable status history; decision/close transitions require cost-manager permission.
- `POST /api/event-kernel/check` — runs local location, time, quantity, method, drawing-version, and three-evidence consistency checks.
- `POST /api/contract` — executes P01 and saves the contract register.
- `POST /api/drawings` — executes P03 and saves the drawing register.
- `POST /api/baseline` — executes P04 and saves the zero ledger.
- `POST /api/changes` — executes P06 and saves the change register.
- `POST /api/evidence` — executes P07 and saves evidence links.
- `POST /api/workspace/import` — imports a versioned local project exchange ZIP and restores project state and available source files.
- `POST /api/boq` — executes P02 through `Runtime.gateway` with standard table rows.
- `POST /api/boq/upload` — accepts a local `.xlsx`, `.xlsm`, or `.csv` file and executes P02 through `Runtime.gateway`.
- `POST /api/cost-plan` — executes P05 through `Runtime.gateway` with P02 items and price books.
- `POST /api/review` — executes P08 through `Runtime.gateway` with the settlement context assembled by the UI.
- `GET /api/workspace/<project_id>/report` — downloads a Word-compatible HTML project report.
- `GET /api/workspace/<project_id>/boq.csv` — downloads the normalized BOQ table as CSV.
- `GET /api/workspace/<project_id>/boq.xlsx` — downloads the normalized BOQ table as XLSX.
- `GET /api/workspace/<project_id>/cost-plan.csv` — downloads an Excel-compatible cost-plan CSV.
- `GET /api/workspace/<project_id>/cost-plan.xlsx` — downloads the cost plan as XLSX.
- `GET /api/workspace/<project_id>/bundle` — downloads the project exchange ZIP.

The nine business entry points mirror the controlled capability contracts:

```text
P01 合同 → P02 清单 → P03 图纸 → P04 零号台账 → P05 成本计划 → P06 变更 → P07 证据 → P08 结算初审
 → P09 成果经营
```

The WebUI exposes standard table input plus `.xlsx`/`.xlsm`/`.csv` file intake. XLSX parsing remains in the P02 capability path; the browser only presents the resulting business table.

Project state is stored under the ignored local `runtime/projects` directory by the workspace adapter. Project source bytes are stored content-addressed under `runtime/sources`, and read-only human-readable category copies are stored under `runtime/archive/<project>/...`; external-basis metadata is stored under `runtime/basis` and its source bytes use the same immutable local source store. Core remains unaware of all these paths.

The project exchange ZIP contains `manifest.json`, `project.json`, normalized BOQ and cost-plan CSVs, a report, source files under `sources/`, and recognized Markdown derivatives under `derived/`. It is intended as a local shared boundary between BuildCostIQ, Excel/CSV, Word-compatible workflows, CAD/quantity tools, and budget software. The current release does not claim live COM, full DWG geometry parsing, or vendor-specific budget-software automation; those integrations can be added behind the connector boundary without changing Core.

## Privacy boundary

Upload, local recognition, classification, Markdown derivation, and project persistence are local operations. The Baidu OCR adapter is disabled by default at the request boundary: the UI requires a per-file confirmation, the API requires `allow_external=true`, and credentials are read only from `BUILDCOSTIQ_BAIDU_API_KEY` and `BUILDCOSTIQ_BAIDU_SECRET_KEY`. Credentials and access tokens are never written to project state. If the credentials are absent, the file remains local and the request returns `not_configured`.

The server binds to `127.0.0.1` by default and serves only the packaged `gui/static` files. It has no external runtime dependency beyond the project's existing `openpyxl` dependency.
