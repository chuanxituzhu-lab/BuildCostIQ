# Local WebUI

BuildCostIQ includes a local WebUI business workbench for all implemented P01–P08 capabilities. It runs on the same frozen Core gateway and does not add a new capability or a database. The visible screen is designed for project users: technical JSON, raw context, and backend return payloads are kept out of the normal workflow.

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

The current `v0.7.2-rc10` intake flow accepts multiple files in one selection. In the BOQ step, table files are sent through P02 and combined when several tables are selected; PDF, Word, PowerPoint, image, CAD, and article files are saved to the project library and reported individually. The header now provides a global “查资料或问问题” entry and the workspace navigation provides “资料与问题”. Search covers local project sources, local recognition Markdown, external-basis snapshots, and saved P01–P08 records. The question mode returns only a local evidence summary with source name, archive path, recognition state, uncertainty labels, and an explicit “no sufficient evidence” outcome; external AI is not called and any future provider must remain behind explicit consent. The project overview continues to provide a project-material search by filename, category, or local path; each result keeps the existing 查看 action so the original file can be opened, including Unicode-named files. P01 is presented as 合同与招采依据 and classifies files into 招标阶段、投标阶段、定标阶段、合同阶段 and 执行解释; relevant category dropdowns group the most-used and recently used three-to-five choices first while keeping other categories available. P03–P08 each have a dedicated material-intake entry with its own logical archive area, while P02 retains its dedicated BOQ intake. Project exports open a second-level export workspace for selecting content, filename, and a local target folder through the browser File System Access API; “下载到默认位置” remains available when folder authorization is unavailable. The project overview has a separate “接入初步资料” entry for initial project information, which uses the same local-first archive and recognition flow.

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

## v0.5.0-rc1 workflow controls

- Every project source has a `查看` action. The original bytes remain in the immutable local source store; a generated Markdown recognition copy can be opened separately when available.
- Every source entry records the absolute local path of the original file and, when present, its Markdown recognition copy. The interface displays both paths and provides a copy-path action; opening an older workspace backfills missing path metadata from its content hash. Upload and workspace responses expose the same `storage_path` metadata for local integrations.
- The first screen is a local registration/login surface. `项目经理` sees KPI-only overview and dashboard screens plus the personnel-management backend entry; `造价经理` has all P01–P08, source, cost, export, soft-delete, audit, and personnel-management permissions; `造价员` can intake, recognize, modify metadata, and edit operational data while sensitive prices and costs are hidden and personnel management is unavailable.
- Source metadata edits, BOQ edits, cost-plan generation, recognition, review runs, views, uploads, and soft deletes append an audit event containing actor, time, target, and relevant details.
- Review findings use red for urgent blockers, yellow for warnings, and blue for notices. The colors are a presentation of the existing rule severity and do not replace evidence.

## API surface

- `GET /api/health` — runtime version and registered P01–P08 capabilities.
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

The eight business entry points mirror the frozen capability contracts:

```text
P01 合同 → P02 清单 → P03 图纸 → P04 零号台账 → P05 成本计划 → P06 变更 → P07 证据 → P08 结算初审
```

The WebUI exposes standard table input plus `.xlsx`/`.xlsm`/`.csv` file intake. XLSX parsing remains in the P02 capability path; the browser only presents the resulting business table.

Project state is stored under the ignored local `runtime/projects` directory by the workspace adapter. Project source bytes are stored content-addressed under `runtime/sources`; external-basis metadata is stored under `runtime/basis` and its source bytes use the same immutable local source store. Core remains unaware of all these paths.

The project exchange ZIP contains `manifest.json`, `project.json`, normalized BOQ and cost-plan CSVs, a report, source files under `sources/`, and recognized Markdown derivatives under `derived/`. It is intended as a local shared boundary between BuildCostIQ, Excel/CSV, Word-compatible workflows, CAD/quantity tools, and budget software. The current release does not claim live COM, full DWG geometry parsing, or vendor-specific budget-software automation; those integrations can be added behind the connector boundary without changing Core.

## Privacy boundary

Upload, local recognition, classification, Markdown derivation, and project persistence are local operations. The Baidu OCR adapter is disabled by default at the request boundary: the UI requires a per-file confirmation, the API requires `allow_external=true`, and credentials are read only from `BUILDCOSTIQ_BAIDU_API_KEY` and `BUILDCOSTIQ_BAIDU_SECRET_KEY`. Credentials and access tokens are never written to project state. If the credentials are absent, the file remains local and the request returns `not_configured`.

The server binds to `127.0.0.1` by default and serves only the packaged `gui/static` files. It has no external runtime dependency beyond the project's existing `openpyxl` dependency.
