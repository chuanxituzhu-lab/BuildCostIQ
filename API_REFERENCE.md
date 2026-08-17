# API Reference

- `Runtime(capabilities)`: registers an explicit capability set and reports health.
- `CapabilityGateway.register(capability)`: accepts unique P01–P08 implementations only.
- `CapabilityGateway.execute(id, context)`: invokes a registered capability with a defensive copy.
- `ImmutableSourceStore.ingest(name, content, media_type)`: stores source bytes by SHA-256 without overwriting existing content.
- `ImmutableSourceStore.read(source)`: reads and verifies source integrity.
- `LocalProjectWorkspace.create(project_id, name)`: creates or resumes a local project workspace.
- `LocalProjectWorkspace.add_source(project_id, source)`: records a source in the project library.
- `LocalProjectWorkspace.set_stage(project_id, stage, result)`: persists a capability result for later resume/export.
- Project stages are stored under `contract`, `boq`, `drawings`, `baseline`, `cost_plan`, `changes`, `evidence`, and `review`.
- `recognition_catalog()`: returns local and consent-gated recognition adapters without exposing credentials.
- `recognize_source(name, content, connector_id, allow_external=False)`: recognizes a source and blocks external transmission unless explicitly allowed.
- `connector_catalog()`: returns the user-facing external-tool connector registry.
- `build_project_bundle(state, source_reader)`: creates a versioned local project exchange ZIP without adding a Core dependency.
- WebUI structured stage endpoints execute P01/P03/P04/P06/P07 through the Gateway at `/api/contract`, `/api/drawings`, `/api/baseline`, `/api/changes`, and `/api/evidence`.


## Review and shared modules

- `review_boq(rows, **references)`: runs every deterministic rule and returns
  `{"findings", "summary", "publishable"}`. Reference inputs are optional; an
  absent reference disables its rule rather than substituting a default.
- `PriceBasis(tax_inclusion, price_type, source, price_date)`: a price book's
  declared basis.
- `comparable(left, right)`: `(COMPARABLE | UNDECLARED | CONFLICTED, reason)`.
- `normalize_unit(value, extra=None)`: folds unit spellings to a canonical symbol.
- `unit_factor(source, target, extra=None)`: conversion multiplier; raises
  `UnitError` across dimensions.
- `find_header_row(rows, max_scan=12)`: locates the BOQ header row by alias hits.
