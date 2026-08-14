"""Local-only registration, login, and role policy for the workbench."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


ROLE_PROJECT_MANAGER = "project_manager"
ROLE_COST_MANAGER = "cost_manager"
ROLE_COST_ESTIMATOR = "cost_estimator"

ROLE_LABELS = {
    ROLE_PROJECT_MANAGER: "项目经理",
    ROLE_COST_MANAGER: "造价经理",
    ROLE_COST_ESTIMATOR: "造价员",
}

# 项目经理与造价经理同属一级；造价员是二级操作角色。
ROLE_LEVELS = {
    ROLE_PROJECT_MANAGER: 1,
    ROLE_COST_MANAGER: 1,
    ROLE_COST_ESTIMATOR: 2,
}

ROLE_DESCRIPTIONS = {
    ROLE_PROJECT_MANAGER: "只看项目重要指标、风险预警与经营趋势",
    ROLE_COST_MANAGER: "完整业务权限，负责造价资料、成本与审计管理",
    ROLE_COST_ESTIMATOR: "负责资料录入和业务操作，敏感价格与成本脱敏",
}

ROLE_PERMISSIONS = {
    ROLE_PROJECT_MANAGER: {
        "view_workspace",
        "view_dashboard",
        "view_kpi",
        "manage_personnel",
    },
    ROLE_COST_MANAGER: {
        "view_workspace",
        "view_dashboard",
        "view_kpi",
        "view_cost_detail",
        "view_source",
        "upload_source",
        "recognize_source",
        "modify_source",
        "delete_source",
        "edit_business_data",
        "view_audit",
        "manage_project",
        "manage_personnel",
        "export_cost",
    },
    ROLE_COST_ESTIMATOR: {
        "view_workspace",
        "view_dashboard",
        "view_source",
        "upload_source",
        "recognize_source",
        "modify_source",
        "edit_business_data",
        "view_audit",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "role_label": ROLE_LABELS[user["role"]],
        "role_level": ROLE_LEVELS[user["role"]],
        "role_description": ROLE_DESCRIPTIONS[user["role"]],
        "can_view_cost_detail": "view_cost_detail" in ROLE_PERMISSIONS[user["role"]],
        "permissions": sorted(ROLE_PERMISSIONS[user["role"]]),
        "created_at": user.get("created_at", ""),
    }


class LocalAuthStore:
    """A small local user registry; passwords never leave this machine."""

    def __init__(self, root: Path | str = "runtime/auth") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "users.json"
        self.personnel_audit_path = self.root / "personnel_audit.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _save(self, users: list[dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def _load_personnel_audit(self) -> list[dict[str, Any]]:
        if not self.personnel_audit_path.exists():
            return []
        payload = json.loads(self.personnel_audit_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _save_personnel_audit(self, events: list[dict[str, Any]]) -> None:
        temporary = self.personnel_audit_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.personnel_audit_path)

    @staticmethod
    def _password_record(password: str, salt: bytes | None = None) -> dict[str, str]:
        if len(password) < 6:
            raise ValueError("密码至少需要 6 位")
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
        return {"salt": salt.hex(), "hash": digest.hex(), "iterations": "210000"}

    @classmethod
    def _verify_password(cls, password: str, record: dict[str, str]) -> bool:
        try:
            salt = bytes.fromhex(record["salt"])
            iterations = int(record.get("iterations", "210000"))
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        except (KeyError, ValueError):
            return False
        return hmac.compare_digest(digest.hex(), str(record.get("hash", "")))

    def register(self, username: str, password: str, role: str) -> dict[str, Any]:
        username = username.strip()
        if len(username) < 2 or len(username) > 64:
            raise ValueError("用户名需要是 2 到 64 个字符")
        if role not in ROLE_LABELS:
            raise ValueError("请选择项目经理、造价经理或造价员角色")
        users = self._load()
        if any(user.get("username", "").lower() == username.lower() for user in users):
            raise ValueError("该用户名已经注册")
        user = {
            "id": str(uuid4()),
            "username": username,
            "role": role,
            "password": self._password_record(password),
            "created_at": _now(),
        }
        users.append(user)
        self._save(users)
        return _public_user(user)

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        user = next((item for item in self._load() if item.get("username", "").lower() == username.lower()), None)
        if user is None or not self._verify_password(password, user.get("password", {})):
            raise ValueError("用户名或密码不正确")
        return _public_user(user)

    def list_public_users(self) -> list[dict[str, Any]]:
        """Return personnel records without password material."""
        return [_public_user(user) for user in self._load()]

    def record_personnel_audit(
        self,
        actor: dict[str, Any],
        action: str,
        target: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid4()),
            "timestamp": _now(),
            "action": action,
            "actor": {
                "id": actor.get("id", ""),
                "username": actor.get("username", ""),
                "role": actor.get("role", ""),
                "role_label": actor.get("role_label", ""),
            },
            "target": target,
            "details": dict(details or {}),
        }
        events = [*self._load_personnel_audit(), event]
        self._save_personnel_audit(events[-500:])
        return event

    def personnel_snapshot(self) -> dict[str, Any]:
        return {"users": self.list_public_users(), "audit_log": self._load_personnel_audit()}
