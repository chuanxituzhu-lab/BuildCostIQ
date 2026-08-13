from __future__ import annotations

from .base import DeclarativeCapability
from .boq import BillOfQuantitiesCapability
from .costplan import CostPlanCapability
from .review import SettlementReviewCapability


def _plugin(capability_id: str, name: str) -> type[DeclarativeCapability]:
    return type(f"{capability_id}Capability", (DeclarativeCapability,), {"capability_id": capability_id, "name": name})


# P02, P05 and P08 have real implementations; the rest keep the declarative
# placeholder until each is filled in turn. The gateway still sees exactly
# P01-P08, so the frozen boundary is unchanged.
PLUGIN_CLASSES = (
    _plugin("P01", "contract"),
    BillOfQuantitiesCapability,
    _plugin("P03", "drawing"),
    _plugin("P04", "baseline-ledger"),
    CostPlanCapability,
    _plugin("P06", "change"),
    _plugin("P07", "evidence"),
    SettlementReviewCapability,
)


def build_default_plugins() -> tuple[DeclarativeCapability, ...]:
    return tuple(plugin() for plugin in PLUGIN_CLASSES)

