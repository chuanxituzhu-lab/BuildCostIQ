from __future__ import annotations

from collections.abc import Iterable

from .gateway import Capability, CapabilityGateway


class Runtime:
    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self.gateway = CapabilityGateway()
        for capability in capabilities:
            self.gateway.register(capability)

    def health(self) -> dict[str, object]:
        return {"status": "ok", "version": "0.7.2-rc10", "capabilities": self.gateway.registered}

