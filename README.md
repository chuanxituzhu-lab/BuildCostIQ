# BuildCostIQ

BuildCostIQ version `v0.3.0-rc1` is a minimal, executable foundation for construction-cost governance. The architecture is frozen around a small Core, independent adapters, and exactly eight plugin capabilities (`P01`–`P08`).

## Quick verification

```bash
python scripts/verify_release.py
```

## Boundaries

- Core owns immutable domain records, provenance hashing, runtime, and the capability gateway.
- Plugins implement P01 contract, P02 bill of quantities, P03 drawings, P04 baseline ledger, P05 cost planning, P06 changes, P07 evidence, and P08 settlement review.
- Adapters handle external storage or future integrations without changing Core.
- P09 and other capability expansion are rejected by the gateway in this release.

The included demo uses sanitized identifiers and contains no real project data.
