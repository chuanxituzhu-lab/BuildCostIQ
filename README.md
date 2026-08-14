# BuildCostIQ

BuildCostIQ version `v0.7.1-rc1` is a local-first construction-cost foundation and full P01–P08 project workbench. The architecture is frozen around a small Core, independent adapters, and exactly eight plugin capabilities (`P01`–`P08`).

## Quick verification

```bash
python scripts/verify_release.py
```

## Local WebUI

Install the project in the existing virtual environment, then start the local review workbench:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m gui --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787/`. The WebUI provides a user-facing project overview, resumable local project workspace, Excel/CSV data intake, project-file library for Office/PDF/CAD/image sources, local recognition and automatic archive classification, business tables, cost planning, settlement review, next-step assistance, and Word/Excel-compatible exports. Its exchange center also imports and exports a portable project ZIP containing local project state, standard tables, report output, original source files, and derived Markdown archives. It uses the frozen P01–P08 gateway and keeps all data local by default; external OCR requires explicit per-file consent and technical JSON is not shown in the normal workflow. After installation, `buildcostiq-web --port 8787` is an equivalent launcher. See [docs/WEBUI.md](docs/WEBUI.md) for the API boundary.

The homepage shows the current release version and release highlights. The workbench now exposes one direct screen for each capability: P01 contract intake, P02 BOQ intake, P03 drawing register, P04 zero ledger, P05 cost planning, P06 change management, P07 evidence linkage, and P08 settlement review. It also provides three role scopes: project managers see important indicators only, cost managers have full permissions, and cost estimators operate the workbench with sensitive prices and costs hidden. It provides role-aware dashboards, local baseline comparison, automated alerts, file viewing, permission-gated edits and soft deletes, multi-file project intake, local recognition, and explicit external OCR consent.

## Boundaries

- Core owns immutable domain records, provenance hashing, runtime, and the capability gateway.
- Plugins implement P01 contract, P02 bill of quantities, P03 drawings, P04 baseline ledger, P05 cost planning, P06 changes, P07 evidence, and P08 settlement review.
- Adapters handle external storage or future integrations without changing Core.
- Source recognition is local-first: PDF/Office/text/CAD metadata are processed locally and retained as derived Markdown; external OCR is a consent-gated adapter and never runs from upload automatically.
- P01–P08 are real implementations; each is executed through the frozen CapabilityGateway and persisted by the adapter-owned project workspace.
- `plugins/normalize.py` and `plugins/basis.py` are shared helper modules, not capabilities.
- P09 and other capability expansion are rejected by the gateway in this release.

The included demo uses sanitized identifiers and contains no real project data.
