# Frozen Plugin Boundaries

| ID | Responsibility | Status |
|---|---|---|
| P01 | Contract intake and interpretation | implemented |
| P02 | Bill-of-quantities intake | implemented |
| P03 | Construction drawing intake | implemented |
| P04 | Baseline (zero) ledger | implemented |
| P05 | Cost planning | implemented |
| P06 | Change management | implemented |
| P07 | Evidence linkage | implemented |
| P08 | Settlement review | implemented |
| P09 | Outcome management projection | implemented |

P09 is a read-only projection over the Core Engineering Event Kernel. It derives the outcome funnel, six value-leak stages, and abnormal queue from existing P01–P08 facts; it does not create a second amount ledger. The independent external-basis catalog (`adapters/basis.py`) remains an adapter-owned local store for P04/P05/P08 references.

The Core Engineering Event Kernel (`core/event_kernel.py`) remains a cross-stage domain model and deterministic rule surface used by P09 and the WebUI to link P01–P08 facts, evidence, state transitions, and local alerts.


## Shared plugin modules (not capabilities)

`plugins/normalize.py` (单位归一与换算) and `plugins/basis.py` (价格口径) are
pure helper modules shared by capabilities. They register nothing with the
gateway and do not widen the P01–P09 boundary.
