"""P01 - contract intake and deterministic interpretation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


class ContractIntakeError(ValueError):
    """Raised when contract intake data cannot form a usable record."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _money(value: object, field: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ContractIntakeError(f"non-numeric {field}: {value!r}") from exc
    if amount < 0:
        raise ContractIntakeError(f"negative {field}: {value!r}")
    return float(amount.quantize(Decimal("0.01")))


class ContractIntakeCapability:
    """Normalize a contract register and its key obligations.

    The capability does not infer legal meaning from a document. It records
    supplied facts, identifies missing fields, and leaves interpretation
    evidence attached to the source boundary for a human to confirm.
    """

    capability_id = "P01"
    name = "contract-intake"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise ContractIntakeError(f"Missing context: {', '.join(missing)}")

        raw = context.get("contract") or context.get("fields") or {}
        if not isinstance(raw, Mapping):
            raise ContractIntakeError("contract must be an object")
        contract = {
            "contract_no": _text(raw.get("contract_no")),
            "title": _text(raw.get("title")),
            "owner": _text(raw.get("owner")),
            "contractor": _text(raw.get("contractor")),
            "contract_amount": _money(raw.get("contract_amount"), "contract_amount"),
            "tax_mode": _text(raw.get("tax_mode")),
            "signed_date": _text(raw.get("signed_date")),
            "start_date": _text(raw.get("start_date")),
            "end_date": _text(raw.get("end_date")),
        }
        obligations_raw = context.get("obligations") or []
        if not isinstance(obligations_raw, Sequence) or isinstance(obligations_raw, (str, bytes, bytearray)):
            raise ContractIntakeError("obligations must be an array")
        obligations: list[dict[str, Any]] = []
        for index, item in enumerate(obligations_raw, start=1):
            if not isinstance(item, Mapping):
                raise ContractIntakeError(f"obligation {index} must be an object")
            name = _text(item.get("name"))
            if not name:
                raise ContractIntakeError(f"obligation {index} needs a name")
            obligations.append(
                {
                    "id": _text(item.get("id")) or f"OB-{index:03d}",
                    "name": name,
                    "owner": _text(item.get("owner")),
                    "due_date": _text(item.get("due_date")),
                    "status": _text(item.get("status")) or "pending",
                    "amount": _money(item.get("amount"), f"obligation {index} amount"),
                }
            )

        required_fields = ("contract_no", "title", "owner", "contractor", "contract_amount", "start_date", "end_date")
        missing_fields = [field for field in required_fields if contract[field] in (None, "")]
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "contract": contract,
            "obligations": obligations,
            "summary": {
                "obligation_count": len(obligations),
                "missing_field_count": len(missing_fields),
                "missing_fields": missing_fields,
                "interpreted": bool(contract["title"] or obligations),
            },
        }
