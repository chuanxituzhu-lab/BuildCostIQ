"""P09 — 全过程成果经营管理。

P09 is a read-only projection over the Core Engineering Event Kernel.  It
does not own events, evidence, prices, or settlement amounts.  Those facts
remain in the existing P01–P08 records; this capability only turns them into
an operational outcome funnel and a small exception queue.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from core import build_outcome_vector, compute_value_leaks, evaluate_event_rules, ensure_outcome_track


_STAGES = (
    ("physical", "实体完成"),
    ("evidence_ready", "证据完整"),
    ("submitted", "已申报"),
    ("confirmed", "已确认"),
    ("revenue", "收入成立"),
    ("settled", "已结算"),
    ("paid", "已回款"),
)

_TERMINAL_OUTCOMES = {"CASH_REALIZED", "REJECTED", "ABANDONED"}


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _date(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _event_status(event: Mapping[str, Any]) -> str:
    governance = event.get("governance")
    governance = governance if isinstance(governance, Mapping) else {}
    return _text(event.get("status") or governance.get("status")) or "DISCOVERED"


def _title(event: Mapping[str, Any]) -> str:
    identity = event.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    return _text(identity.get("title")) or _text(event.get("event_id")) or "工程事件"


class OutcomeManagementCapability:
    """Derive the management view from append-only event/outcome facts."""

    capability_id = "P09"
    name = "outcome-management"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        project_id = _text(context.get("project_id"))
        if not project_id:
            raise ValueError("Missing context: project_id")
        raw_events = context.get("events") or []
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes, bytearray)):
            raise ValueError("events must be an array")

        events = [ensure_outcome_track(item) for item in raw_events if isinstance(item, Mapping)]
        stage_totals = {stage: Decimal("0") for stage, _ in _STAGES}
        stage_counts: Counter[str] = Counter()
        status_counts: Counter[str] = Counter()
        type_counts: Counter[str] = Counter()
        leaks: list[dict[str, Any]] = []
        queue: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for event in events:
            outcome = event.get("outcome_track") or {}
            outcome = outcome if isinstance(outcome, Mapping) else {}
            outcome_vector = build_outcome_vector(event)
            outcome_status = _text(outcome_vector.get("status")) or "NOT_FORMED"
            status_counts[outcome_status] += 1
            for outcome_type in outcome_vector.get("types") or []:
                type_counts[_text(outcome_type)] += 1
            values = outcome.get("values") if isinstance(outcome.get("values"), Mapping) else {}
            for stage, _ in _STAGES:
                amount = _number(values.get(stage))
                if amount is not None:
                    stage_totals[stage] += Decimal(str(amount))
                    stage_counts[stage] += 1

            event_leaks = compute_value_leaks(event)
            event_title = _title(event)
            for leak in event_leaks.get("items") or []:
                leaks.append({
                    **dict(leak),
                    "title": event_title,
                    "severity": _text((event.get("classification") or {}).get("severity")) if isinstance(event.get("classification"), Mapping) else "",
                })

            alerts = evaluate_event_rules(event)
            discovered_at = _date((event.get("origin") or {}).get("discovered_at")) if isinstance(event.get("origin"), Mapping) else None
            days_open = max(0, (now - discovered_at).days) if discovered_at else None
            if alerts or outcome_status not in _TERMINAL_OUTCOMES:
                queue.append({
                    "event_id": _text(event.get("event_id")),
                    "title": event_title,
                    "event_status": _event_status(event),
                    "outcome_status": outcome_status,
                    "value_leak_count": int(outcome_vector.get("value_leak_count", 0) or 0),
                    "alert_count": len(alerts),
                    "days_open": days_open,
                    "time_stage": outcome_status if outcome_status != "NOT_FORMED" else _event_status(event),
                    "priority": len(alerts) * 10 + int(event_leaks.get("total", 0) or 0),
                })

        funnel: list[dict[str, Any]] = []
        previous: Decimal | None = None
        for stage, label in _STAGES:
            amount = stage_totals[stage]
            conversion = None if previous in (None, Decimal("0")) else float((amount / previous) * 100)
            funnel.append({
                "stage": stage,
                "label": label,
                "amount": round(float(amount), 2),
                "event_count": stage_counts[stage],
                "conversion_rate": conversion,
            })
            if amount > 0:
                previous = amount

        leaks.sort(key=lambda item: item.get("amount", 0), reverse=True)
        queue.sort(key=lambda item: item.get("priority", 0), reverse=True)
        fact_sources = context.get("facts") if isinstance(context.get("facts"), Mapping) else {}
        source_status = {
            capability_id: "ready" if fact_sources.get(capability_id) else "missing"
            for capability_id in (f"P{i:02d}" for i in range(1, 9))
        }
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": project_id,
            "status": "accepted",
            "summary": {
                "event_count": len(events),
                "open_event_count": len(queue),
                "outcome_count": sum(count for status, count in status_counts.items() if status != "NOT_FORMED"),
                "value_leak_count": len(leaks),
                "value_leak_total": round(sum(float(item.get("amount", 0) or 0) for item in leaks), 2),
            },
            "value_leak_total": round(sum(float(item.get("amount", 0) or 0) for item in leaks), 2),
            "value_leak_count": len(leaks),
            "funnel": funnel,
            "status_counts": dict(status_counts),
            "type_counts": dict(type_counts),
            "value_leaks": leaks[:12],
            "daily_queue": queue[:12],
            "fact_sources": source_status,
            "forecast": {
                "status": "insufficient_data",
                "reason": "当前项目尚未提供实际成本、剩余工程成本和风险权重；系统不猜测 EAC 利润。",
                "available": ["confirmed", "submitted", "settled", "paid"],
                "missing": ["actual_cost", "remaining_cost", "risk_weight"],
            },
            "rules": {
                "single_fact_source": True,
                "event_closed_not_outcome_closed": True,
                "derived_values_only": True,
                "append_only": True,
            },
        }


__all__ = ["OutcomeManagementCapability"]
