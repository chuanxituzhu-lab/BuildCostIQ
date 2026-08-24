"""P05 — Cost planning (real implementation).

P05 prices the bill-of-quantities items produced by P02 and rolls them up into
a plan cost. It follows a strict contract-control discipline:

* The **winning-bid (中标) unit price is the authoritative basis.** Any BOQ item
  whose code appears in the contract price book is priced at that rate and its
  amount enters the CONTRACT subtotal. These rates are never altered here.

* **Missing items are flagged, never guessed.** A BOQ item with no contract rate
  is marked ``re-priced-pending``: its unit price is left null and its amount is
  zero. Such items are counted and listed so nothing is lost, but re-pricing
  (组价) is a later, deliberate step — P05 does not invent a number. Their count
  forms a separate PENDING subtotal, kept apart from the contract total.

* **Market price is internal cost control only, and physically isolated.** An
  optional market price book produces a per-item and total variance
  (contract − market) under a separate ``cost_control`` section. Market figures
  never touch any external subtotal or total. This separation is structural:
  the external roll-up is computed solely from contract rates, so a market
  number cannot leak into billable cost even by mistake.

Pure, side-effect-free computation. Inputs are plain data; output rows record
directly as Evidence(kind="cost_plan_item") / Evidence(kind="cost_control").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .basis import CONFLICTED, as_basis, comparable


# Pricing status of each planned item.
STATUS_CONTRACT = "contract"            # priced at the winning-bid rate
STATUS_PENDING = "re-priced-pending"    # not in contract; awaits deliberate 组价
STATUS_UNPRICED = "unpriced"            # explicitly has no basis and none pending

_CENT = Decimal("0.01")


class CostPlanError(ValueError):
    """Raised when cost-planning inputs are structurally invalid."""


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - normalize any parse failure
        raise CostPlanError(f"non-numeric {field}: {value!r}") from exc


def _money(value: Decimal) -> float:
    """Quantize to 2 decimals (currency) with half-up rounding, return float."""
    return float(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _index_price_book(price_book: Mapping[str, object]) -> dict[str, Decimal]:
    """Normalize a {code: unit_price} mapping to Decimal, validating values."""
    indexed: dict[str, Decimal] = {}
    for code, rate in price_book.items():
        rate_dec = _to_decimal(rate, f"unit price for {code}")
        if rate_dec < 0:
            raise CostPlanError(f"negative unit price for {code}: {rate}")
        indexed[str(code).strip()] = rate_dec
    return indexed


def plan_costs(
    items: Sequence[Mapping[str, Any]],
    contract_prices: Mapping[str, object],
    market_prices: Mapping[str, object] | None = None,
    contract_basis: Any = None,
    market_basis: Any = None,
) -> dict[str, Any]:
    """Price BOQ items against the contract basis and roll up a plan.

    Args:
        items: BOQ line items from P02, each with at least ``code`` and
            ``quantity`` (and typically name/feature/unit).
        contract_prices: authoritative {code: 中标综合单价}.
        market_prices: optional {code: 市场综合单价}, used ONLY for the
            isolated internal cost-control variance.

    Returns a mapping with priced ``items``, external ``summary`` (contract and
    pending kept separate), and an isolated ``cost_control`` section.
    """
    contract = _index_price_book(contract_prices)
    market = _index_price_book(market_prices) if market_prices else {}

    priced: list[dict[str, Any]] = []
    contract_total = Decimal("0")
    pending_count = 0

    for item in items:
        code = str(item.get("code", "")).strip()
        if not code:
            raise CostPlanError(f"BOQ item missing code: {item!r}")
        quantity = _to_decimal(item.get("quantity", 0), f"quantity for {code}")

        row: dict[str, Any] = {
            "code": code,
            "name": item.get("name", ""),
            "unit": item.get("unit", ""),
            "quantity": float(quantity),
        }

        if code in contract:
            rate = contract[code]
            amount = rate * quantity
            row["status"] = STATUS_CONTRACT
            row["unit_price"] = _money(rate)
            row["amount"] = _money(amount)
            row["price_basis"] = "winning-bid"
            contract_total += amount
        else:
            # No contract basis: flag and suspend. Do NOT fabricate a price.
            row["status"] = STATUS_PENDING
            row["unit_price"] = None
            row["amount"] = 0.0
            row["price_basis"] = "requires-re-pricing"
            pending_count += 1

        priced.append(row)

    # External summary: contract and pending are reported SEPARATELY.
    summary = {
        "contract_item_count": sum(1 for r in priced if r["status"] == STATUS_CONTRACT),
        "contract_subtotal": _money(contract_total),
        "pending_item_count": pending_count,
        "pending_subtotal": 0.0,  # pending items carry no billable amount yet
        "total_item_count": len(priced),
    }

    # Isolated internal cost control — market variance never enters the summary,
    # and is only computed when the two price books are on a comparable basis.
    cost_control = (
        _build_cost_control(priced, contract, market, contract_basis, market_basis)
        if market
        else None
    )

    return {"items": priced, "summary": summary, "cost_control": cost_control}


def _build_cost_control(
    priced: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Decimal],
    market: Mapping[str, Decimal],
    contract_basis: Any = None,
    market_basis: Any = None,
) -> dict[str, Any]:
    """Internal-only: contract vs market variance. Never affects external totals.

    价格口径闸门：含税价减除税价在算术上成立、在造价上无效，且错得安静。
    两本价册声明了口径且冲突时，本函数**拒绝出偏差数** —— 返回结构完整但
    不含数字的结果，附上理由。口径未声明时照旧出数，但打上 ``undeclared``
    标记（保持对既有调用方的向后兼容，同时把问题显性化）。
    """
    status, reason = comparable(as_basis(contract_basis), as_basis(market_basis))
    if status == CONFLICTED:
        return {
            "note": "internal cost control only — not part of external cost plan",
            "comparability": status,
            "reason": reason,
            "items": [],
            "total_variance": None,
        }

    rows: list[dict[str, Any]] = []
    total_variance = Decimal("0")
    for row in priced:
        code = row["code"]
        if code not in contract or code not in market:
            continue
        quantity = _to_decimal(row["quantity"], f"quantity for {code}")
        variance = (contract[code] - market[code]) * quantity  # +ve = margin
        total_variance += variance
        rows.append(
            {
                "code": code,
                "contract_unit_price": _money(contract[code]),
                "market_unit_price": _money(market[code]),
                "quantity": row["quantity"],
                "variance_amount": _money(variance),
            }
        )
    return {
        "note": "internal cost control only — not part of external cost plan",
        "comparability": status,
        "reason": reason,
        "items": rows,
        "total_variance": _money(total_variance),
    }


class CostPlanCapability:
    """P05 — Cost planning.

    Context keys:
        project_id (str, required)
        source_id  (str, required)
        items      (list, optional) — BOQ items from P02; empty is a valid
                                       "nothing to price yet" state.
        contract_prices (dict, optional) — {code: 中标综合单价}, the basis.
        market_prices   (dict, optional) — {code: 市场综合单价}, internal only.
        contract_basis  (dict, optional) — 合同价册口径（税制/类型/出处/取价期）。
        market_basis    (dict, optional) — 市场价册口径。口径冲突时不出偏差数。

    Returns the priced plan with separate contract/pending subtotals and an
    isolated cost-control section, ready to record as Evidence.
    """

    capability_id = "P05"
    name = "cost-plan"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        required = ("project_id", "source_id")
        missing = [key for key in required if not context.get(key)]
        if missing:
            raise ValueError(f"Missing context: {', '.join(missing)}")

        items = context.get("items") or []
        contract_prices = context.get("contract_prices") or {}
        market_prices = context.get("market_prices")

        plan = plan_costs(
            items,
            contract_prices,
            market_prices,
            contract_basis=context.get("contract_basis"),
            market_basis=context.get("market_basis"),
        )

        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "items": plan["items"],
            "summary": plan["summary"],
            "cost_control": plan["cost_control"],
        }
