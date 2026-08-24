"""P04 - zero/baseline ledger."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


class BaselineLedgerError(ValueError):
    """Raised when baseline ledger data is invalid."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: object, field: str, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise BaselineLedgerError(f"{field} is required")
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BaselineLedgerError(f"non-numeric {field}: {value!r}") from exc
    if number < 0:
        raise BaselineLedgerError(f"negative {field}: {value!r}")
    return number


class BaselineLedgerCapability:
    capability_id = "P04"
    name = "baseline-ledger"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise BaselineLedgerError(f"Missing context: {', '.join(missing)}")
        raw = context.get("entries") or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            raise BaselineLedgerError("entries must be an array")
        entries: list[dict[str, Any]] = []
        total = Decimal("0")
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, Mapping):
                raise BaselineLedgerError(f"entry {index} must be an object")
            name = _text(item.get("name"))
            if not name:
                raise BaselineLedgerError(f"entry {index} needs a name")
            quantity = _number(item.get("quantity"), f"entry {index} quantity")
            unit_price = _number(item.get("unit_price"), f"entry {index} unit_price")
            amount = _number(item.get("amount"), f"entry {index} amount")
            if amount is None and quantity is not None and unit_price is not None:
                amount = quantity * unit_price
            if amount is None:
                amount = Decimal("0")
            amount = amount.quantize(Decimal("0.01"))
            total += amount
            entries.append(
                {
                    "entry_id": _text(item.get("entry_id")) or f"BL-{index:03d}",
                    "code": _text(item.get("code")),
                    "name": name,
                    "unit": _text(item.get("unit")),
                    "quantity": float(quantity) if quantity is not None else None,
                    "unit_price": float(unit_price) if unit_price is not None else None,
                    "amount": float(amount),
                    "basis": _text(item.get("basis")) or "未声明",
                    "source_id": _text(item.get("source_id")) or context["source_id"],
                    "status": _text(item.get("status")) or "baseline",
                }
            )
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "entries": entries,
            "summary": {
                "entry_count": len(entries),
                "baseline_total": float(total.quantize(Decimal("0.01"))),
                "source_count": len({item["source_id"] for item in entries}),
                "unpriced_count": sum(item["unit_price"] is None for item in entries),
            },
        }
