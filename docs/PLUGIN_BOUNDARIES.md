# Frozen Plugin Boundaries

| ID | Responsibility | Status |
|---|---|---|
| P01 | Contract intake and interpretation | declarative |
| P02 | Bill-of-quantities intake | implemented |
| P03 | Construction drawing intake | declarative |
| P04 | Baseline (zero) ledger | declarative |
| P05 | Cost planning | implemented |
| P06 | Change management | declarative |
| P07 | Evidence linkage | declarative |
| P08 | Settlement review | implemented |

No additional plugin capability is part of v0.5.0-rc1. New integrations must be adapters and must not modify Core or create a new business capability.


## Shared plugin modules (not capabilities)

`plugins/normalize.py` (单位归一与换算) and `plugins/basis.py` (价格口径) are
pure helper modules shared by capabilities. They register nothing with the
gateway and therefore do not widen the frozen P01–P08 boundary.
