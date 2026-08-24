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
from .outcome import OutcomeManagementCapability

# P01-P08 own professional facts. P09 is a read-only projection over the Core
# event/outcome kernel; persistence and external file handling remain in adapters.
PLUGIN_CLASSES = (
    ContractIntakeCapability,
    BillOfQuantitiesCapability,
    DrawingIntakeCapability,
    BaselineLedgerCapability,
    CostPlanCapability,
    ChangeManagementCapability,
    EvidenceLinkageCapability,
    SettlementReviewCapability,
    OutcomeManagementCapability,
)


def build_default_plugins() -> tuple[DeclarativeCapability, ...]:
    return tuple(plugin() for plugin in PLUGIN_CLASSES)

