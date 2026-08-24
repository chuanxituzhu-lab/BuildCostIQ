"""Local external-basis catalog kept outside the frozen Core capabilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


BASIS_CATEGORIES: tuple[dict[str, str], ...] = (
    {"id": "policy", "label": "政策法规", "description": "政策、法规、计价管理办法、税费和合同示范文本。"},
    {"id": "pricing_basis", "label": "定额与计价依据", "description": "定额、清单计价规范、费用定额、编码和换算规则。"},
    {"id": "price_info", "label": "造价信息", "description": "人材机信息价、指数、调价文件和地区价格。"},
    {"id": "market_price", "label": "市场价格", "description": "厂商报价、询价记录和市场价格快照。"},
    {"id": "interface_snapshot", "label": "外部接口快照", "description": "政府或第三方接口取得的本地版本快照。"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalBasisWorkspace:
    """Persist independent basis metadata while source bytes stay immutable."""

    def __init__(self, root: Path | str = "runtime/basis") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "catalog.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _save(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(self.path)
        return items

    def list(self) -> list[dict[str, Any]]:
        return list(self._load())

    def get(self, basis_id: str) -> dict[str, Any] | None:
        return next((item for item in self._load() if item.get("basis_id") == basis_id), None)

    def add(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(metadata)
        item.setdefault("basis_id", f"basis-{uuid4().hex[:12]}")
        item.setdefault("created_at", _now())
        items = [entry for entry in self._load() if entry.get("basis_id") != item["basis_id"]]
        items.append(item)
        self._save(items)
        return item

