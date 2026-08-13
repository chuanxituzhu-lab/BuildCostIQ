# Changelog

Project: BuildCostIQ

## v0.4.0-rc1 — 2026-08-13

- Extended the workbench intake control to accept multiple files in one selection, including PDF, Word, PowerPoint, images, CAD, Excel, CSV, and project documents.
- Added project setup intake for initial project information files; uploaded photos, Word, Excel, PDF, and related materials are saved to the local project and automatically recognized/classified.
- Added per-file intake feedback so users can see whether a file was converted locally, recognized, needs OCR, or is currently unsupported.
- Added local-first PDF/Office/text/CAD recognition and Markdown archive derivatives while preserving the original source file.
- Kept external OCR behind explicit per-file consent; no external transfer occurs during upload or local recognition.
- Updated the homepage to display the active version and release highlights.

## Unreleased

- Implemented P08 (settlement / BOQ review) as a real capability, replacing the
  declarative placeholder. Deterministic rule engine only — arithmetic and
  consistency defects (合价校验, 编码格式与重复, 工程量, 单位错配, 单价偏离,
  漏项覆盖) are decided by rules, not by a model. Every finding carries a
  `rule_id` and an `evidence` basis and records as
  Evidence(kind="review_finding"). Severities are block/warn/info; a single
  `block` sets `publishable=False`. All reference inputs (unit catalogue, price
  book, quantity ceilings, expected divisions) are injected — nothing is
  assumed, and a rule that has no reference simply does not fire.
- Added `plugins/basis.py`: price-basis (口径) governance. A unit price is only
  meaningful under a declared 税制 / 价格类型 / 出处 / 取价期. `comparable()`
  distinguishes *undeclared* from *conflicted* and refuses the subtraction in
  the latter case.
- Added `plugins/normalize.py`: unit normalisation (㎡/m²/平方米 → m2) and
  quota-multiplier conversion (100m3 → m3 = ×100), with cross-dimension pairs
  refused rather than silently computed.
- **Fix (P05):** the market-vs-contract variance was computed without any check
  that the two price books share a tax basis. Subtracting a 含税 market price
  from a 除税 contract price is arithmetically valid and 造价-wise wrong, and it
  failed silently. `cost_control` now reports `comparability` and returns no
  variance number when the declared bases conflict. External totals are
  unchanged; undeclared bases stay backward-compatible.
- **Fix (P02):** `parse_standard_boq` assumed `rows[0]` was the header. Real
  清单 exports put 工程名称/标段/编制单位 banner rows above the table, so the
  parser failed on the most common input shape. `find_header_row` now locates
  the header by alias-hit scoring over the first 12 rows.
- Added `tests/test_review.py` (28 tests) and `examples/review_workflow.py`.

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
