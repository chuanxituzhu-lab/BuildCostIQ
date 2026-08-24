"""Deterministic evidence projection for role work products.

P07 remains the only persisted evidence-link fact owner.  This adapter does
not create a second evidence store and does not mutate sources or products; it
only projects explainable matches from the existing project sources, role
product keys, and saved P07 links.  A unique key match is an automatic
projection.  Ties and weak matches remain visible for human confirmation.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


EVIDENCE_INTAKE_VERSION = "1.0"

_KEY_FIELDS = (
    "document_ref",
    "material_batch",
    "daily_log_ref",
    "photo_refs",
    "sample_id",
    "report_ref",
    "drawing_version",
    "document_no",
    "wbs",
    "location",
    "control_point",
    "survey_task",
    "request_id",
    "order_ref",
    "source_refs",
    "evidence_refs",
)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _product_keys(product: Mapping[str, Any]) -> list[str]:
    fields = _mapping(product.get("fields"))
    links = _mapping(product.get("links"))
    keys: list[str] = []
    for name in _KEY_FIELDS:
        keys.extend(_values(fields.get(name)))
        if name in {"source_refs", "evidence_refs"}:
            keys.extend(_values(links.get(name)))
    # Stable de-duplication avoids counting the same reference twice.
    return list(dict.fromkeys(item for item in keys if len(item) >= 3))


def _source_text(source: Mapping[str, Any]) -> str:
    recognition = _mapping(source.get("recognition"))
    parts = [
        source.get("source_id"),
        source.get("name"),
        source.get("kind"),
        source.get("archive_path"),
        source.get("archive_category"),
        recognition.get("text"),
        recognition.get("category"),
    ]
    return " ".join(_text(item).lower() for item in parts if _text(item))


def _saved_source_links(state: Mapping[str, Any]) -> set[str]:
    result = _mapping(state.get("evidence")).get("result")
    links = _mapping(result).get("links") or []
    return {
        _text(item.get("source_id"))
        for item in links
        if isinstance(item, Mapping) and _text(item.get("source_id"))
    }


def derive_evidence_intake(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> list[dict[str, Any]]:
    selected = set(roles or [])
    sources = [item for item in state.get("sources") or [] if isinstance(item, Mapping)]
    source_ids = {_text(item.get("source_id")) for item in sources if _text(item.get("source_id"))}
    saved_sources = _saved_source_links(state)
    result: list[dict[str, Any]] = []
    for product in state.get("role_work_products") or []:
        if not isinstance(product, Mapping):
            continue
        role = _text(product.get("role"))
        if selected and role not in selected:
            continue
        keys = _product_keys(product)
        explicit_refs = set(_values(_mapping(product.get("links")).get("source_refs"))).intersection(source_ids)
        candidates: list[dict[str, Any]] = []
        for source in sources:
            source_id = _text(source.get("source_id"))
            if not source_id:
                continue
            text = _source_text(source)
            matched = sorted({key for key in keys if key.lower() in text})
            if not matched:
                continue
            candidates.append({
                "source_id": source_id,
                "name": _text(source.get("name")) or source_id,
                "score": len(matched),
                "matched_keys": matched,
                "saved_in_p07": source_id in saved_sources,
            })
        candidates.sort(key=lambda item: (-int(item["score"]), item["source_id"]))
        top_score = int(candidates[0]["score"]) if candidates else 0
        top = [item for item in candidates if int(item["score"]) == top_score and top_score]
        if explicit_refs or any(item.get("saved_in_p07") for item in candidates):
            status = "LINKED"
            reason = "岗位成果已保留来源引用，P07 只做既有链条归档"
            requires_confirmation = False
        elif len(top) == 1 and top_score >= 1:
            status = "AUTO_MATCHED"
            reason = "唯一来源键命中，底层自动投影；不复制原件"
            requires_confirmation = False
        elif len(top) > 1:
            status = "REVIEW_REQUIRED"
            reason = "多个来源同时命中，需责任岗位人工确认"
            requires_confirmation = True
        else:
            status = "UNLINKED"
            reason = "没有稳定来源键，保持待补充，不猜测关联"
            requires_confirmation = True
        result.append({
            "intake_id": f"EVIDENCE-{_text(product.get('product_id'))}",
            "product_id": _text(product.get("product_id")),
            "role": role,
            "product_type": _text(product.get("product_type")),
            "status": status,
            "requires_manual_confirmation": requires_confirmation,
            "candidate_sources": candidates[:5],
            "keys": keys,
            "reason": reason,
        })
    return result


def evidence_intake_snapshot(state: Mapping[str, Any], roles: Sequence[str] | None = None) -> dict[str, Any]:
    selected = list(roles or [])
    intake = derive_evidence_intake(state, selected)
    return {
        "version": EVIDENCE_INTAKE_VERSION,
        "policy": "deterministic_source_key_location_and_batch_projection",
        "fact_owner": "P07",
        "auto_projection": True,
        "auto_write_p07": False,
        "human_confirmation_required_for": "ambiguous_or_unlinked",
        "intake": intake,
    }
