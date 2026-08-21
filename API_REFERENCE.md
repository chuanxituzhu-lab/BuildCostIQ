# API Reference

P09 is a read-only derived capability. GET /api/p09?project_id=... returns its outcome funnel, six value-leak stages, abnormal daily queue, fact-source coverage, and boundary rules.

- `Runtime(capabilities)`: registers an explicit capability set and reports health.
- `CapabilityGateway.register(capability)`: accepts unique P01–P09 implementations only; P09 is read-only and derived.
- `CapabilityGateway.execute(id, context)`: invokes a registered capability with a defensive copy.
- `ImmutableSourceStore.ingest(name, content, media_type)`: stores source bytes by SHA-256 without overwriting existing content.
- `ImmutableSourceStore.read(source)`: reads and verifies source integrity.
- `LocalProjectWorkspace.create(project_id, name)`: creates or resumes a local project workspace.
- `LocalProjectWorkspace.add_source(project_id, source)`: records a source in the project library.
- `LocalProjectWorkspace.set_stage(project_id, stage, result)`: persists a capability result for later resume/export.
- `DeploymentConfig` / `DeploymentStorageAdapter`: bind adapter-owned stores to one data root and serialize project read-modify-write transactions; use `BUILDCOSTIQ_DEPLOYMENT_MODE=central` for a multi-terminal authoritative node.
- `GET /api/deployment`: returns deployment mode, logical storage roots, authority and consistency policy without exposing absolute filesystem paths.
- Project stages are stored under `contract`, `boq`, `drawings`, `baseline`, `cost_plan`, `changes`, `evidence`, and `review`.
- `recognition_catalog()`: returns local and consent-gated recognition adapters without exposing credentials.
- `recognize_source(name, content, connector_id, allow_external=False)`: recognizes a source and blocks external transmission unless explicitly allowed.
- `connector_catalog()`: returns the user-facing external-tool connector registry.
- `build_project_bundle(state, source_reader)`: creates a versioned local project exchange ZIP without adding a Core dependency.
- WebUI structured stage endpoints execute P01/P03/P04/P06/P07 through the Gateway at `/api/contract`, `/api/drawings`, `/api/baseline`, `/api/changes`, and `/api/evidence`.
- `new_event(...)` creates a permanent Event with an append-only `outcome_track`; `transition_event(...)` and `transition_outcome(...)` are independent guarded state machines.
- `record_outcome_snapshot(event, changes, actor=...)` appends a revision for Outcome metadata/value snapshots without replacing prior history.
- `compute_value_leaks(event)` derives the six conversion gaps from existing P01–P08 value snapshots; it is diagnostic output, not a second amount source.
- `POST /api/event-kernel/outcome` accepts `operation=snapshot` or `operation=transition`; `GET /api/dashboard` exposes the derived `outcome_management` funnel, leak list, and abnormal `daily_queue`.
- Personnel governance is local and role-driven: `GET /api/personnel` and `POST /api/personnel` are available to project managers and explicitly authorized administrative officers; `POST /api/personnel/authorize` is project-manager-only; `POST /api/personnel/delete` removes an active record while retaining the audit event. `POST /api/personnel/rename` changes only the login/display name while retaining `user_id`, password, role, audit and project records, so the successor can log in with the new name and continue the old account. `POST /api/personnel/roles` supports separate or merged `surveyor` + `site_engineer` assignments. The role and assignment catalogs are returned in the personnel snapshot.
- `GET /api/workspace?project_id=...` returns a role-scoped projection with `visible_views`; non-manager roles do not receive unrelated P01–P08 stage payloads. The WebUI uses the same catalog to render independent role workbenches. P01–P08 write endpoints additionally check the assigned role capability, so a hidden tab cannot be bypassed by calling another role's work surface.


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
