from __future__ import annotations

from .base import DeclarativeCapability
from .baseline import BaselineLedgerCapability
from .boq import BillOfQuantitiesCapability
from .changes import ChangeManagementCapability
from .contract import ContractIntakeCapability
from .costplan import CostPlanCapability
from .drawings import DrawingIntakeCapability
from .evidence import EvidenceLinkageCapability
from .review import SettlementReviewCapability

# All eight frozen capabilities have a pure implementation. Persistence and
# external file handling remain in adapters; the gateway boundary is unchanged.
PLUGIN_CLASSES = (
    ContractIntakeCapability,
    BillOfQuantitiesCapability,
    DrawingIntakeCapability,
    BaselineLedgerCapability,
    CostPlanCapability,
    ChangeManagementCapability,
    EvidenceLinkageCapability,
    SettlementReviewCapability,
)


def build_default_plugins() -> tuple[DeclarativeCapability, ...]:
    return tuple(plugin() for plugin in PLUGIN_CLASSES)

