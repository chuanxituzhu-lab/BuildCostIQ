from __future__ import annotations

from collections.abc import Iterable

from .gateway import Capability, CapabilityGateway
from .version import current_version


class Runtime:
    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self.gateway = CapabilityGateway()
        for capability in capabilities:
            self.gateway.register(capability)

    def health(self) -> dict[str, object]:
        return {"status": "ok", "version": current_version(), "capabilities": self.gateway.registered}

