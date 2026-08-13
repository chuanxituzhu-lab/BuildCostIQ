# Local WebUI

BuildCostIQ includes a local WebUI business workbench for the implemented P02 → P05 → P08 path. It runs on the same frozen Core gateway and does not add a new capability or a database. The visible screen is designed for project users: technical JSON, raw context, and backend return payloads are kept out of the normal workflow.

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

The current `v0.4.0-rc1` intake flow accepts multiple files in one selection. In the BOQ step, table files are sent through P02 and combined when several tables are selected; PDF, Word, PowerPoint, image, CAD, and article files are saved to the project library and reported individually. The project overview has a separate “接入初步资料” entry for initial project information, which uses the same local-first archive and recognition flow.

## API surface

- `GET /api/health` — runtime version and registered P01–P08 capabilities.
- `GET /api/architecture` — the frozen layer map, capability statuses, shared helpers, and invariants used by the UI.
- `GET /api/sample` — sanitized seed data used by the user-facing demo screen.
- `GET /api/connectors` — the external-tool connector catalog and supported directions/formats.
- `GET /api/recognition/catalog` — local recognizers and external providers, including whether explicit consent is required.
- `POST /api/project` — creates or updates a local project workspace.
- `GET /api/workspace?project_id=...` — resumes the saved project state.
- `POST /api/source/upload` — saves a generic project source in the immutable source store and project library.
- `POST /api/source/recognize` — reruns local recognition or requests an explicitly authorized external recognition call for one source.
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

The three business entry points intentionally mirror the frozen capability contracts:

```text
P02 清单 intake → P05 成本计划 → P08 结算初审
```

The WebUI exposes standard table input plus `.xlsx`/`.xlsm`/`.csv` file intake. XLSX parsing remains in the P02 capability path; the browser only presents the resulting business table.

Project state is stored under the ignored local `runtime/projects` directory by the workspace adapter. Source bytes are stored content-addressed under `runtime/sources`; Core remains unaware of both paths.

The project exchange ZIP contains `manifest.json`, `project.json`, normalized BOQ and cost-plan CSVs, a report, source files under `sources/`, and recognized Markdown derivatives under `derived/`. It is intended as a local shared boundary between BuildCostIQ, Excel/CSV, Word-compatible workflows, CAD/quantity tools, and budget software. The current release does not claim live COM, full DWG geometry parsing, or vendor-specific budget-software automation; those integrations can be added behind the connector boundary without changing Core.

## Privacy boundary

Upload, local recognition, classification, Markdown derivation, and project persistence are local operations. The Baidu OCR adapter is disabled by default at the request boundary: the UI requires a per-file confirmation, the API requires `allow_external=true`, and credentials are read only from `BUILDCOSTIQ_BAIDU_API_KEY` and `BUILDCOSTIQ_BAIDU_SECRET_KEY`. Credentials and access tokens are never written to project state. If the credentials are absent, the file remains local and the request returns `not_configured`.

The server binds to `127.0.0.1` by default and serves only the packaged `gui/static` files. It has no external runtime dependency beyond the project's existing `openpyxl` dependency.
