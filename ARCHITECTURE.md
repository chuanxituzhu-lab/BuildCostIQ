# Phase 10C M0 Frozen Architecture

Scope: one construction project department, one Project Server product, Skills 01–09 only.

Five layers: Experience (apps/webui role workspace); Coordination (platform/coordinator + workflow); Professional (domains + skills 01–09); Integration (connectors); Shared truth services (the existing local project JSON/workspace, content-addressed sources, audit and the new hash-linked execution ledger). The single-project scope retains the current file-based storage; PostgreSQL is not planned or required.

No sixth layer. Server owns permission decisions. UI does not calculate quantities or amounts. All formal results follow Candidate -> Review -> Human Gate -> Confirmed -> Canonical. Agents, connectors and file imports cannot directly promote. A latest record never becomes Canonical automatically.

M0 is declarative and disabled. Database migration is a comment-only marker; there is no new API, worker, scheduler, installer or UI. YAML/JSON/MCP/CLI remain developer implementation details; ordinary user flow is Open -> Input -> Execute -> Result.

## Compatibility and reuse

Existing core/, plugins/, adapters/, gui/, migrations/, runtime/, examples/, docker/ and packaging are preserved, excluded from new-directory creation freeze. They are legacy reuse candidates, not proof of Phase 10 conformity. Original architecture below describes that legacy implementation. In particular old P09 outcome projection is NOT new Skill 09 quality evidence. M1 must audit ownership, eight-role mapping and single-project isolation before wiring.

## Contracts and ownership

contracts/ describes project-scoped events, immutable evidence metadata, candidate-only connector responses, denied-by-default permissions, disabled capability/product registries and workflows. workflows/templates and skills contain exactly nine disabled descriptors. Every executable handler remains null. Provisional IDs and incomplete original freeze evidence block production wiring; see docs/m0/M1_ENTRY.md.

---

## Legacy architecture retained for migration review

# Architecture

## P09 outcome projection
P09 is the read-only management projection over the Core Engineering Event Kernel. P01–P08 remain the professional fact owners. P09 is executed through the same CapabilityGateway, exposes GET /api/p09, and derives the outcome funnel, value leaks, and exception queue without persisting a second ledger.

The dependency direction is `GUI / adapters / plugins -> Core`; Core does not import business plugins or external adapters. `CapabilityGateway` is the sole capability execution boundary and accepts P01–P09. P01–P08 own professional facts; P09 is a read-only projection over the Core Engineering Event Kernel, which owns permanent event identity, append-only state history, baseline impact, production/technical/commercial tracks, three-evidence checks, an independent Outcome state machine, derived Value Leak stages, settlement lifecycle, and deterministic local rules. Source bytes are content-addressed by SHA-256 and verified on read. Evidence records retain project and source identifiers and expose an immutable payload.

The GUI is a project workbench rather than a second business engine. It owns project navigation, data editing, file intake, result presentation, work assistance, and Office-compatible exports. Every P01–P08 capability now has a direct WebUI screen; the UI only assembles context and presents the Gateway result. `LocalProjectWorkspace` persists resumable project state outside Core. `ImmutableSourceStore` preserves original Excel, Word, PDF, CAD, image, and other source bytes. `adapters/recognition.py` is a local-first recognition boundary: it creates classified metadata and Markdown derivatives without replacing originals; external OCR adapters require explicit per-file consent. `adapters/connectors.py` provides the connector catalog and a versioned local project exchange package; the WebUI can export/import that package with derived recognition artifacts without changing Core records. New external tools should connect through adapters/connectors or recognition adapters; they must not make Core depend on their file formats, network calls, or application rules. CAD and budget-software integrations currently use the shared project package boundary, while direct `.xlsx`/`.csv`, PDF extraction, local Office/text conversion, and Word-compatible report paths are available in the workbench. The event-kernel WebUI follows a three-step evidence policy: local project data is distilled first, user text is distilled second, and the fusion result retains both sources plus conflicts and claims; it never calls an external AI provider. Each Event also carries an append-only `outcome_track` projection with an independent Outcome state machine. It references existing P01–P08 value facts through snapshots and derives the six-stage Value Leak funnel; it is not a new capability or a second amount ledger.

## Deployment and storage boundary

`adapters/deployment.py` is outside Core and P01–P09. It binds all adapter-owned stores to one deployment data root, publishes the node mode through `GET /api/deployment`, and coordinates per-project read-modify-write transactions with thread and process locks. In central mode, one WebUI/API service is authoritative and project terminals use browsers; a shared folder is never treated as a live database. The default single-node mode remains local-first. `projects/` stores project state, `sources/` stores immutable content-addressed originals, `archive/` stores human-readable copies, `basis/` stores external-basis metadata, `auth/` stores identity and role data, `backups/` is for recovery copies, and `locks/` protects project writes. Project revisions provide an explicit consistency marker; future offline edge sync must submit versioned, auditable packets and route professional conflicts to human responsibility-line confirmation.

