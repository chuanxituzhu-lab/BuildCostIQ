from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class Capability(Protocol):
    capability_id: str

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]: ...


class CapabilityGateway:
    """Single controlled entry point for the P01-P09 capability boundary."""

    ALLOWED = frozenset(f"P{i:02d}" for i in range(1, 10))

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        capability_id = capability.capability_id
        if capability_id not in self.ALLOWED:
            raise ValueError(f"Capability {capability_id} is outside the P01-P09 boundary")
        if capability_id in self._capabilities:
            raise ValueError(f"Capability {capability_id} is already registered")
        self._capabilities[capability_id] = capability

    def execute(self, capability_id: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        if capability_id not in self._capabilities:
            raise KeyError(f"Capability {capability_id} is not registered")
        return self._capabilities[capability_id].execute(MappingProxy(context))

    @property
    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))


class MappingProxy(dict[str, Any]):
    """Defensive shallow copy passed to plugins."""

    def __init__(self, source: Mapping[str, Any]) -> None:
        super().__init__(source)
