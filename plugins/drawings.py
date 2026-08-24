"""P03 - construction drawing register intake."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class DrawingIntakeError(ValueError):
    """Raised when a drawing register row is incomplete."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


class DrawingIntakeCapability:
    capability_id = "P03"
    name = "drawing-intake"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise DrawingIntakeError(f"Missing context: {', '.join(missing)}")
        raw = context.get("drawings") or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            raise DrawingIntakeError("drawings must be an array")
        drawings: list[dict[str, Any]] = []
        seen: set[str] = set()
        duplicate_count = 0
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, Mapping):
                raise DrawingIntakeError(f"drawing {index} must be an object")
            drawing_no = _text(item.get("drawing_no"))
            name = _text(item.get("name"))
            if not drawing_no or not name:
                raise DrawingIntakeError(f"drawing {index} needs drawing_no and name")
            key = f"{drawing_no}|{_text(item.get('revision'))}"
            if key in seen:
                duplicate_count += 1
            seen.add(key)
            drawings.append(
                {
                    "drawing_no": drawing_no,
                    "name": name,
                    "discipline": _text(item.get("discipline")) or "general",
                    "revision": _text(item.get("revision")) or "A",
                    "status": _text(item.get("status")) or "received",
                    "source_id": _text(item.get("source_id")) or context["source_id"],
                    "review_note": _text(item.get("review_note")),
                }
            )
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "drawings": drawings,
            "summary": {
                "drawing_count": len(drawings),
                "revision_count": len({item["revision"] for item in drawings}),
                "duplicate_count": duplicate_count,
                "unreviewed_count": sum(item["status"] not in {"reviewed", "approved"} for item in drawings),
            },
        }
