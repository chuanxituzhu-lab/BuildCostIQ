# Changelog

Project: BuildCostIQ

## Unreleased

- Implemented P05 (cost planning) as a real capability. Prices P02's BOQ items
  against the winning-bid (中标) unit price as the authoritative basis; items
  absent from the contract price book are flagged `re-priced-pending` with a
  null price and zero amount — never guessed. The external summary keeps the
  contract subtotal and the pending items strictly separate. An optional market
  price book feeds an isolated `cost_control` variance (contract − market) that
  can never enter any external total. Currency maths use Decimal (half-up).
  Records as Evidence(kind="cost_plan_item"). Core and the frozen boundary
  unchanged.
- Added `examples/contract_prices.sample.json` and `examples/market_prices.sample.json`.

- Implemented P02 (bill-of-quantities) as a real capability: parses GB 50500
  standard BOQ tables and, in merge mode, consolidates 广联达-style per-component
  quantity sheets via a JSON mapping table. Output rows carry the five clause
  elements (code/name/feature/unit/quantity) and record directly as
  Evidence(kind="boq_item"). Pure openpyxl parsing — no Excel process, no
  pickle, no GUI. Core, gateway, and the frozen P01–P08 boundary are unchanged.
- Added `openpyxl>=3.1` dependency and `examples/boq_mapping.sample.json`.

## v0.3.0-rc1

- Added frozen Core runtime and capability gateway.
- Added P01–P08 plugin contracts and default implementations.
- Added immutable source storage, evidence provenance, tests, CI, Docker, and sanitized demo workflow.
