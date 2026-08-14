"""P06 - change management register."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


class ChangeManagementError(ValueError):
    """Raised when a change row cannot be evaluated."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _amount(value: object, field: str) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ChangeManagementError(f"non-numeric {field}: {value!r}") from exc


class ChangeManagementCapability:
    capability_id = "P06"
    name = "change-management"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise ChangeManagementError(f"Missing context: {', '.join(missing)}")
        raw = context.get("changes") or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            raise ChangeManagementError("changes must be an array")
        changes: list[dict[str, Any]] = []
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, Mapping):
                raise ChangeManagementError(f"change {index} must be an object")
            title = _text(item.get("title"))
            if not title:
                raise ChangeManagementError(f"change {index} needs a title")
            amount = _amount(item.get("amount"), f"change {index} amount")
            changes.append(
                {
                    "change_id": _text(item.get("change_id")) or f"CH-{index:03d}",
                    "title": title,
                    "reason": _text(item.get("reason")),
                    "amount": float(amount),
                    "status": _text(item.get("status")) or "pending",
                    "impact_date": _text(item.get("impact_date")),
                    "owner": _text(item.get("owner")),
                    "source_id": _text(item.get("source_id")) or context["source_id"],
                    "risk_note": _text(item.get("risk_note")),
                }
            )
        net = sum((Decimal(str(item["amount"])) for item in changes), Decimal("0"))
        approved = [item for item in changes if item["status"] in {"approved", "implemented"}]
        pending = [item for item in changes if item["status"] == "pending"]
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "changes": changes,
            "summary": {
                "change_count": len(changes),
                "approved_count": len(approved),
                "pending_count": len(pending),
                "net_amount": float(net.quantize(Decimal("0.01"))),
                "requires_decision": bool(pending),
            },
        }
