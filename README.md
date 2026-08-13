# BuildCostIQ

BuildCostIQ version `v0.6.0-rc1` is a local-first construction-cost foundation and project workbench. The architecture is frozen around a small Core, independent adapters, and exactly eight plugin capabilities (`P01`–`P08`).

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

The homepage shows the current release version and the current release highlights: role-aware project intelligence dashboards, local baseline comparison, automated cost-over-limit and review-cadence alerts, file viewing with recorded local original and recognition-copy paths, permission-gated edits and soft deletes with audit trails, multi-file project intake, local recognition, and explicit external OCR consent.

## Boundaries

- Core owns immutable domain records, provenance hashing, runtime, and the capability gateway.
- Plugins implement P01 contract, P02 bill of quantities, P03 drawings, P04 baseline ledger, P05 cost planning, P06 changes, P07 evidence, and P08 settlement review.
- Adapters handle external storage or future integrations without changing Core.
- Source recognition is local-first: PDF/Office/text/CAD metadata are processed locally and retained as derived Markdown; external OCR is a consent-gated adapter and never runs from upload automatically.
- P02, P05 and P08 are real implementations; P01/P03/P04/P06/P07 remain declarative placeholders.
- `plugins/normalize.py` and `plugins/basis.py` are shared helper modules, not capabilities.
- P09 and other capability expansion are rejected by the gateway in this release.

The included demo uses sanitized identifiers and contains no real project data.
