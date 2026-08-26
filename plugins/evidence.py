"""P07 - evidence linkage across project records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class EvidenceLinkageError(ValueError):
    """Raised when an evidence link is incomplete."""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


class EvidenceLinkageCapability:
    capability_id = "P07"
    name = "evidence-linkage"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise EvidenceLinkageError(f"Missing context: {', '.join(missing)}")
        raw = context.get("links") or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            raise EvidenceLinkageError("links must be an array")
        links: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        duplicate_count = 0
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, Mapping):
                raise EvidenceLinkageError(f"link {index} must be an object")
            target_type = _text(item.get("target_type"))
            target_id = _text(item.get("target_id"))
            relation = _text(item.get("relation")) or "supports"
            if not target_type or not target_id:
                raise EvidenceLinkageError(f"link {index} needs target_type and target_id")
            key = (_text(item.get("source_id")) or context["source_id"], target_type, target_id)
            if key in seen:
                duplicate_count += 1
            seen.add(key)
            verified = item.get("verified", False)
            if isinstance(verified, str):
                verified = verified.strip().lower() in {"1", "true", "yes", "y", "已核验"}
            links.append(
                {
                    "link_id": _text(item.get("link_id")) or f"EV-{index:03d}",
                    "source_id": key[0],
                    "target_type": target_type,
                    "target_id": target_id,
                    "relation": relation,
                    "note": _text(item.get("note")),
                    "verified": bool(verified),
                }
            )
        target_types = sorted({item["target_type"] for item in links})
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "links": links,
            "summary": {
                "link_count": len(links),
                "verified_count": sum(item["verified"] for item in links),
                "unverified_count": sum(not item["verified"] for item in links),
                "duplicate_count": duplicate_count,
                "target_types": target_types,
            },
        }
