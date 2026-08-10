from __future__ import annotations

from .base import DeclarativeCapability


def _plugin(capability_id: str, name: str) -> type[DeclarativeCapability]:
    return type(f"{capability_id}Capability", (DeclarativeCapability,), {"capability_id": capability_id, "name": name})


PLUGIN_CLASSES = (
    _plugin("P01", "contract"),
    _plugin("P02", "bill-of-quantities"),
    _plugin("P03", "drawing"),
    _plugin("P04", "baseline-ledger"),
    _plugin("P05", "cost-plan"),
    _plugin("P06", "change"),
    _plugin("P07", "evidence"),
    _plugin("P08", "settlement-review"),
)


def build_default_plugins() -> tuple[DeclarativeCapability, ...]:
    return tuple(plugin() for plugin in PLUGIN_CLASSES)

