from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class DeclarativeCapability:
    capability_id = ""
    name = ""

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        required = ("project_id", "source_id")
        missing = [key for key in required if not context.get(key)]
        if missing:
            raise ValueError(f"Missing context: {', '.join(missing)}")
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
        }

