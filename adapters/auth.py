"""Local-only registration, login, and role policy for the workbench."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4


ROLE_PROJECT_MANAGER = "project_manager"
ROLE_COST_MANAGER = "cost_manager"
ROLE_COST_ESTIMATOR = "cost_estimator"
ROLE_TECHNICAL_LEAD = "technical_lead"
ROLE_PRODUCTION_MANAGER = "production_manager"
ROLE_SITE_ENGINEER = "site_engineer"
ROLE_SURVEYOR = "surveyor"
ROLE_QUALITY_OFFICER = "quality_officer"
ROLE_LAB_TESTING_OFFICER = "lab_testing_officer"
ROLE_DOCUMENT_CONTROLLER = "document_controller"
ROLE_SAFETY_OFFICER = "safety_officer"
ROLE_PROCUREMENT_OFFICER = "procurement_officer"
ROLE_WAREHOUSE_OFFICER = "warehouse_officer"
ROLE_ADMINISTRATIVE_OFFICER = "administrative_officer"

# The order is deliberately stable: it is used by the personnel form and by
# the local acceptance/demo reset.  Administrative officer is a governance
# role, not a municipal production line role.
PERSONNEL_ROLE_ORDER = (
    ROLE_PROJECT_MANAGER,
    ROLE_COST_MANAGER,
    ROLE_COST_ESTIMATOR,
    ROLE_TECHNICAL_LEAD,
    ROLE_PRODUCTION_MANAGER,
    ROLE_SITE_ENGINEER,
    ROLE_SURVEYOR,
    ROLE_QUALITY_OFFICER,
    ROLE_LAB_TESTING_OFFICER,
    ROLE_DOCUMENT_CONTROLLER,
    ROLE_SAFETY_OFFICER,
    ROLE_PROCUREMENT_OFFICER,
    ROLE_WAREHOUSE_OFFICER,
    ROLE_ADMINISTRATIVE_OFFICER,
)

ROLE_LABELS = {
    ROLE_PROJECT_MANAGER: "项目经理",
    ROLE_COST_MANAGER: "造价经理",
    ROLE_COST_ESTIMATOR: "造价员",
    ROLE_TECHNICAL_LEAD: "技术负责人",
    ROLE_PRODUCTION_MANAGER: "生产经理",
    ROLE_SITE_ENGINEER: "施工员/测量员",
    ROLE_SURVEYOR: "测量员",
    ROLE_QUALITY_OFFICER: "质量负责人",
    ROLE_LAB_TESTING_OFFICER: "试验检测员",
    ROLE_DOCUMENT_CONTROLLER: "资料员",
    ROLE_SAFETY_OFFICER: "安全员",
    ROLE_PROCUREMENT_OFFICER: "采购员",
    ROLE_WAREHOUSE_OFFICER: "仓管员",
    ROLE_ADMINISTRATIVE_OFFICER: "行政人员",
}

# 项目经理与造价经理同属一级；造价员是二级操作角色。
ROLE_LEVELS = {
    ROLE_PROJECT_MANAGER: 1,
    ROLE_COST_MANAGER: 1,
    ROLE_COST_ESTIMATOR: 2,
    ROLE_TECHNICAL_LEAD: 2,
    ROLE_PRODUCTION_MANAGER: 2,
    ROLE_SITE_ENGINEER: 3,
    ROLE_SURVEYOR: 3,
    ROLE_QUALITY_OFFICER: 2,
    ROLE_LAB_TESTING_OFFICER: 3,
    ROLE_DOCUMENT_CONTROLLER: 2,
    ROLE_SAFETY_OFFICER: 2,
    ROLE_PROCUREMENT_OFFICER: 2,
    ROLE_WAREHOUSE_OFFICER: 3,
    ROLE_ADMINISTRATIVE_OFFICER: 2,
}

ROLE_DESCRIPTIONS = {
    ROLE_PROJECT_MANAGER: "只看项目重要指标、风险预警与经营趋势",
    ROLE_COST_MANAGER: "完整业务权限，负责造价资料、成本与审计管理",
    ROLE_COST_ESTIMATOR: "负责资料录入和业务操作，敏感价格与成本脱敏",
    ROLE_TECHNICAL_LEAD: "负责技术方案、图纸、规范和技术确认",
    ROLE_PRODUCTION_MANAGER: "负责生产计划、现场进度和实物量确认",
    ROLE_SITE_ENGINEER: "负责现场记录、施工过程和实测资料",
    ROLE_SURVEYOR: "负责测量放样、实测数据和测量成果",
    ROLE_QUALITY_OFFICER: "负责质量检查、验收和质量证据",
    ROLE_LAB_TESTING_OFFICER: "负责试验检测、报告和检测证据",
    ROLE_DOCUMENT_CONTROLLER: "负责资料归档、版本和成果包管理",
    ROLE_SAFETY_OFFICER: "负责安全检查、隐患和安全证据",
    ROLE_PROCUREMENT_OFFICER: "负责采购、供应商和到货依据",
    ROLE_WAREHOUSE_OFFICER: "负责仓储、收发料和材料台账",
    ROLE_ADMINISTRATIVE_OFFICER: "负责项目行政协同；人员管理须经项目经理授权",
}

ROLE_PERMISSIONS = {
    ROLE_PROJECT_MANAGER: {
        "view_workspace",
        "view_dashboard",
        "view_kpi",
        "manage_personnel",
        "authorize_personnel_admin",
    },
    ROLE_COST_MANAGER: {
        "view_workspace",
        "view_dashboard",
        "view_kpi",
        "view_cost_detail",
        "view_source",
        "view_basis",
        "upload_source",
        "upload_basis",
        "recognize_source",
        "modify_source",
        "delete_source",
        "edit_business_data",
        "view_audit",
        "manage_project",
        "export_cost",
        "reference_basis",
    },
    ROLE_COST_ESTIMATOR: {
        "view_workspace",
        "view_dashboard",
        "view_source",
        "view_basis",
        "upload_source",
        "upload_basis",
        "recognize_source",
        "modify_source",
        "edit_business_data",
        "view_audit",
        "reference_basis",
    },
    ROLE_TECHNICAL_LEAD: {"view_workspace", "edit_business_data", "view_audit"},
    ROLE_PRODUCTION_MANAGER: {"view_workspace", "view_dashboard", "edit_business_data", "view_audit"},
    ROLE_SITE_ENGINEER: {"view_workspace", "edit_business_data"},
    ROLE_SURVEYOR: {"view_workspace", "edit_business_data"},
    ROLE_QUALITY_OFFICER: {"view_workspace", "edit_business_data", "view_audit"},
    ROLE_LAB_TESTING_OFFICER: {"view_workspace", "edit_business_data"},
    ROLE_DOCUMENT_CONTROLLER: {"view_workspace", "view_audit", "upload_source"},
    ROLE_SAFETY_OFFICER: {"view_workspace", "edit_business_data", "view_audit"},
    ROLE_PROCUREMENT_OFFICER: {"view_workspace", "edit_business_data"},
    ROLE_WAREHOUSE_OFFICER: {"view_workspace", "edit_business_data"},
    ROLE_ADMINISTRATIVE_OFFICER: {"view_workspace"},
}

ROLE_ALIASES = {
    "estimator": ROLE_COST_ESTIMATOR,
    "construction_worker": ROLE_SITE_ENGINEER,
    "施工员": ROLE_SITE_ENGINEER,
    "现场施工员": ROLE_SITE_ENGINEER,
    "现场工程师": ROLE_SITE_ENGINEER,
    "施工员/测量员": ROLE_SITE_ENGINEER,
    "施工员/现场工程师": ROLE_SITE_ENGINEER,
}

MERGEABLE_FIELD_ROLES = (ROLE_SURVEYOR, ROLE_SITE_ENGINEER)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_role(role: str) -> str:
    normalized = ROLE_ALIASES.get(str(role).strip(), str(role).strip())
    if normalized not in ROLE_LABELS:
        raise ValueError("请选择有效的项目岗位角色")
    return normalized


def _normalize_roles(roles: list[str] | tuple[str, ...] | None, primary: str) -> list[str]:
    values = list(roles or [primary])
    normalized = []
    for role in values:
        canonical = _normalize_role(role)
        if canonical not in normalized:
            normalized.append(canonical)
    if primary not in normalized:
        normalized.insert(0, primary)
    if len(normalized) > 1 and set(normalized) != set(MERGEABLE_FIELD_ROLES):
        raise ValueError("当前仅支持将测量员与施工员合并为一个岗位组合")
    return normalized


class PersonnelPolicyError(PermissionError):
    """Raised when a personnel governance action violates the local policy."""


class LocalAuthStore:
    """A small local user registry; passwords never leave this machine."""

    def __init__(self, root: Path | str = "runtime/auth") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "users.json"
        self.personnel_audit_path = self.root / "personnel_audit.json"
        self.personnel_grants_path = self.root / "personnel_grants.json"
        self.project_memberships_path = self.root / "project_memberships.json"
        self.project_personnel_audit_path = self.root / "project_personnel_audit.json"
        self.basic_personnel_ids_path = self.root / "basic_personnel_ids.json"
        self.project_invites_path = self.root / "project_invites.json"
        self._mutation_lock = RLock()

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

    def _load_personnel_grants(self) -> set[str]:
        if not self.personnel_grants_path.exists():
            return set()
        payload = json.loads(self.personnel_grants_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("authorized_user_ids", [])
        return {str(item) for item in payload if str(item).strip()}

    def _save_personnel_grants(self, user_ids: set[str]) -> None:
        temporary = self.personnel_grants_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps({"authorized_user_ids": sorted(user_ids)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.personnel_grants_path)

    def _load_project_memberships(self) -> dict[str, list[str]]:
        if not self.project_memberships_path.exists():
            return {}
        payload = json.loads(self.project_memberships_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {
            str(project_id): [str(user_id) for user_id in user_ids if str(user_id).strip()]
            for project_id, user_ids in payload.items()
            if isinstance(user_ids, list)
        }

    def _save_project_memberships(self, memberships: dict[str, list[str]]) -> None:
        temporary = self.project_memberships_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(memberships, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.project_memberships_path)

    def _load_project_personnel_audit(self) -> dict[str, list[dict[str, Any]]]:
        if not self.project_personnel_audit_path.exists():
            return {}
        payload = json.loads(self.project_personnel_audit_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {
            str(project_id): [dict(item) for item in events if isinstance(item, dict)][-500:]
            for project_id, events in payload.items()
            if isinstance(events, list)
        }

    def _save_project_personnel_audit(self, audits: dict[str, list[dict[str, Any]]]) -> None:
        temporary = self.project_personnel_audit_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.project_personnel_audit_path)

    def _load_project_invites(self) -> dict[str, list[dict[str, Any]]]:
        if not self.project_invites_path.exists():
            return {}
        payload = json.loads(self.project_invites_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {
            str(project_id): [dict(item) for item in invites if isinstance(item, dict)][-500:]
            for project_id, invites in payload.items()
            if isinstance(invites, list)
        }

    def _save_project_invites(self, invites: dict[str, list[dict[str, Any]]]) -> None:
        temporary = self.project_invites_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(invites, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.project_invites_path)

    def _load_basic_personnel_ids(self) -> set[str]:
        if not self.basic_personnel_ids_path.exists():
            return set()
        payload = json.loads(self.basic_personnel_ids_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("user_ids", [])
        return {str(user_id) for user_id in payload if str(user_id).strip()} if isinstance(payload, list) else set()

    def _save_basic_personnel_ids(self, user_ids: set[str] | list[str] | tuple[str, ...]) -> None:
        temporary = self.basic_personnel_ids_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"user_ids": sorted({str(user_id) for user_id in user_ids})}, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.basic_personnel_ids_path)

    def ensure_project_membership(self, project_id: str) -> list[str]:
        """Create an isolated project roster, seeded from the current basic roster."""
        project_id = str(project_id or "").strip()
        if not project_id:
            return []
        memberships = self._load_project_memberships()
        available = {str(user.get("id")) for user in self._load() if str(user.get("id", "")).strip()}
        if project_id not in memberships:
            basic_ids = self._load_basic_personnel_ids()
            seed_ids = basic_ids.intersection(available) if basic_ids else available
            memberships[project_id] = sorted(seed_ids)
            self._save_project_memberships(memberships)
        else:
            filtered = [user_id for user_id in memberships[project_id] if user_id in available]
            if filtered != memberships[project_id]:
                memberships[project_id] = filtered
                self._save_project_memberships(memberships)
        return list(memberships.get(project_id, []))

    def add_user_to_project(self, project_id: str, user_id: str) -> None:
        project_id = str(project_id or "").strip()
        user_id = str(user_id or "").strip()
        if not project_id or not user_id:
            raise ValueError("项目和人员不能为空")
        memberships = self._load_project_memberships()
        member_ids = self.ensure_project_membership(project_id)
        if user_id not in member_ids:
            memberships = self._load_project_memberships()
            memberships.setdefault(project_id, member_ids).append(user_id)
            self._save_project_memberships(memberships)

    def remove_user_from_project(self, project_id: str, user_id: str) -> None:
        project_id = str(project_id or "").strip()
        user_id = str(user_id or "").strip()
        memberships = self._load_project_memberships()
        member_ids = self.ensure_project_membership(project_id)
        if user_id not in member_ids:
            raise ValueError("目标人员不在当前项目名册")
        memberships = self._load_project_memberships()
        memberships[project_id] = [item for item in member_ids if item != user_id]
        self._save_project_memberships(memberships)

    def _project_has_user(self, project_id: str, user_id: str) -> bool:
        return str(user_id) in set(self.ensure_project_membership(project_id))

    @staticmethod
    def _invite_status(invite: Mapping[str, Any], now: datetime | None = None) -> str:
        status = str(invite.get("status", "ACTIVE")).upper()
        if status == "ACTIVE":
            try:
                expires_at = datetime.fromisoformat(str(invite.get("expires_at", "")).replace("Z", "+00:00"))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= (now or datetime.now(timezone.utc)):
                    return "EXPIRED"
            except ValueError:
                return "EXPIRED"
        return status

    def _invite_public(self, invite: Mapping[str, Any]) -> dict[str, Any]:
        role = _normalize_role(str(invite.get("role", "")))
        return {
            "invite_id": str(invite.get("invite_id", "")),
            "project_id": str(invite.get("project_id", "")),
            "role": role,
            "role_label": ROLE_LABELS[role],
            "created_by": dict(invite.get("created_by") or {}),
            "created_at": str(invite.get("created_at", "")),
            "expires_at": str(invite.get("expires_at", "")),
            "status": self._invite_status(invite),
            "accepted_by": dict(invite.get("accepted_by") or {}) if invite.get("accepted_by") else None,
            "accepted_at": str(invite.get("accepted_at", "")),
            "revoked_at": str(invite.get("revoked_at", "")),
        }

    def _require_invite_manager(self, actor: dict[str, Any], project_id: str) -> None:
        if "manage_personnel" not in set(actor.get("permissions", [])):
            raise PersonnelPolicyError("当前角色没有生成岗位邀请的权限")
        if not self._project_has_user(project_id, str(actor.get("id", ""))):
            raise PersonnelPolicyError("当前账号不是该项目成员，不能生成项目岗位邀请")

    def create_project_invite(
        self,
        actor: dict[str, Any],
        project_id: str,
        role: str,
        expires_hours: int = 72,
    ) -> dict[str, Any]:
        project_id = str(project_id or "").strip()
        if not project_id:
            raise ValueError("项目标识不能为空")
        self._require_invite_manager(actor, project_id)
        role = _normalize_role(role)
        try:
            expires_hours = int(expires_hours)
        except (TypeError, ValueError) as exc:
            raise ValueError("邀请有效期必须是整数小时") from exc
        if not 1 <= expires_hours <= 720:
            raise ValueError("邀请有效期应为 1 到 720 小时")
        with self._mutation_lock:
            created_at = _now()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
            raw_token = secrets.token_urlsafe(32)
            invite = {
                "invite_id": f"INV-{uuid4().hex[:12].upper()}",
                "project_id": project_id,
                "role": role,
                "token_hash": hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                "created_by": {key: actor.get(key, "") for key in ("id", "username", "role", "role_label")},
                "created_at": created_at,
                "expires_at": expires_at,
                "status": "ACTIVE",
                "accepted_by": None,
                "accepted_at": "",
                "revoked_at": "",
            }
            invites = self._load_project_invites()
            invites.setdefault(project_id, []).append(invite)
            invites[project_id] = invites[project_id][-500:]
            self._save_project_invites(invites)
            self.record_personnel_audit(
                dict(actor),
                "personnel.invite_created",
                invite["invite_id"],
                {"project_id": project_id, "role": role, "expires_at": expires_at},
                project_id=project_id,
            )
            result = self._invite_public(invite)
            result["token"] = raw_token
            result["accept_path"] = f"/?invite={raw_token}"
            return result

    def list_project_invites(self, actor: dict[str, Any], project_id: str) -> dict[str, Any]:
        project_id = str(project_id or "").strip()
        if not project_id:
            raise ValueError("项目标识不能为空")
        self._require_invite_manager(actor, project_id)
        invites = self._load_project_invites().get(project_id, [])
        return {"project_id": project_id, "invites": [self._invite_public(item) for item in reversed(invites)]}

    def revoke_project_invite(self, actor: dict[str, Any], project_id: str, invite_id: str) -> dict[str, Any]:
        project_id = str(project_id or "").strip()
        invite_id = str(invite_id or "").strip()
        if not project_id or not invite_id:
            raise ValueError("项目和邀请编号不能为空")
        self._require_invite_manager(actor, project_id)
        with self._mutation_lock:
            invites = self._load_project_invites()
            target = next((item for item in invites.get(project_id, []) if str(item.get("invite_id")) == invite_id), None)
            if target is None:
                raise ValueError("岗位邀请不存在")
            if self._invite_status(target) != "ACTIVE":
                raise ValueError("只有有效中的岗位邀请可以撤销")
            target["status"] = "REVOKED"
            target["revoked_at"] = _now()
            self._save_project_invites(invites)
            self.record_personnel_audit(dict(actor), "personnel.invite_revoked", invite_id, {"project_id": project_id}, project_id=project_id)
            return {"project_id": project_id, "invite": self._invite_public(target), "invites": [self._invite_public(item) for item in reversed(invites[project_id])]}

    def accept_project_invite(self, token: str, username: str, password: str) -> dict[str, Any]:
        token = str(token or "").strip()
        username = str(username or "").strip()
        password = str(password or "")
        if not token or not username:
            raise ValueError("邀请链接、姓名/登录名不能为空")
        if not password:
            raise ValueError("请设置登录密码")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._mutation_lock:
            invites = self._load_project_invites()
            target = next((item for values in invites.values() for item in values if hmac.compare_digest(str(item.get("token_hash", "")), token_hash)), None)
            if target is None:
                raise ValueError("岗位邀请不存在或链接无效")
            if self._invite_status(target) != "ACTIVE":
                raise ValueError("岗位邀请已过期、撤销或使用过")
            users = self._load()
            existing = next((item for item in users if str(item.get("username", "")).casefold() == username.casefold()), None)
            if existing is not None:
                if not self._verify_password(password, existing.get("password", {})):
                    raise ValueError("该姓名/登录名已存在，请使用原账号密码接受邀请")
                invited_role = _normalize_role(str(target.get("role", "")))
                existing_roles = _normalize_roles(existing.get("roles"), str(existing.get("role", "")))
                if invited_role not in existing_roles:
                    raise ValueError("该账号当前岗位与邀请岗位不一致，请由项目经理先调整岗位后再接受邀请")
                user = self._public_user(existing)
            else:
                user = self.register(username, password, str(target.get("role", "")))
            project_id = str(target.get("project_id", ""))
            self.add_user_to_project(project_id, str(user["id"]))
            target["status"] = "ACCEPTED"
            target["accepted_by"] = {"id": user["id"], "username": user["username"], "role": user["role"]}
            target["accepted_at"] = _now()
            self._save_project_invites(invites)
            self.record_personnel_audit(
                {"id": user["id"], "username": user["username"], "role": user["role"], "role_label": user["role_label"]},
                "personnel.invite_accepted",
                str(target.get("invite_id", "")),
                {"project_id": project_id, "user_id": user["id"], "role": target.get("role", "")},
                project_id=project_id,
            )
            return {"user": user, "project_id": project_id, "role": target.get("role", ""), "invite": self._invite_public(target)}

    def _public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        role = _normalize_role(str(user.get("role", "")))
        assigned_roles = _normalize_roles(user.get("roles"), role)
        permissions = set().union(*(ROLE_PERMISSIONS[item] for item in assigned_roles))
        authorized = role == ROLE_ADMINISTRATIVE_OFFICER and user["id"] in self._load_personnel_grants()
        if authorized:
            permissions.add("manage_personnel")
        return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", user["username"]),
        "role": role,
        "role_label": ROLE_LABELS[role],
        "roles": assigned_roles,
        "role_labels": [ROLE_LABELS[item] for item in assigned_roles],
        "role_assignment": "merged" if set(assigned_roles) == set(MERGEABLE_FIELD_ROLES) else "separate",
        "role_level": ROLE_LEVELS[role],
        "role_description": "；".join(ROLE_DESCRIPTIONS[item] for item in assigned_roles),
        "can_view_cost_detail": "view_cost_detail" in permissions,
        "permissions": sorted(permissions),
        "can_manage_personnel": "manage_personnel" in permissions,
        "personnel_admin_authorized": authorized,
        "name_history": list(user.get("name_history") or []),
        "created_at": user.get("created_at", ""),
        }

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

    def register(
        self,
        username: str,
        password: str,
        role: str,
        roles: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        # Invite acceptance and the public registration endpoint share this
        # mutation.  The re-entrant lock makes a token one-time even when two
        # browser requests arrive at the same moment.
        with self._mutation_lock:
            username = username.strip()
            if len(username) < 1 or len(username) > 64:
                raise ValueError("用户名需要是 1 到 64 个字符")
            role = _normalize_role(role)
            assigned_roles = _normalize_roles(roles, role)
            users = self._load()
            if any(user.get("username", "").lower() == username.lower() for user in users):
                raise ValueError("该用户名已经注册")
            user = {
                "id": str(uuid4()),
                "username": username,
                "display_name": username,
                "role": role,
                "roles": assigned_roles,
                "password": self._password_record(password),
                "created_at": _now(),
            }
            users.append(user)
            self._save(users)
            return self._public_user(user)

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        user = next((item for item in self._load() if item.get("username", "").lower() == username.lower()), None)
        if user is None or not self._verify_password(password, user.get("password", {})):
            raise ValueError("用户名或密码不正确")
        return self._public_user(user)

    def list_public_users(self) -> list[dict[str, Any]]:
        """Return personnel records without password material."""
        return [self._public_user(user) for user in self._load()]

    def public_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        user = next((item for item in self._load() if str(item.get("id")) == str(user_id)), None)
        return self._public_user(user) if user else None

    def personnel_role_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "role": role,
                "label": ROLE_LABELS[role],
                "level": ROLE_LEVELS[role],
                "description": ROLE_DESCRIPTIONS[role],
            }
            for role in PERSONNEL_ROLE_ORDER
        ]

    def personnel_assignment_catalog(self) -> dict[str, Any]:
        return {
            "separate": [
                {"role": role, "label": ROLE_LABELS[role]}
                for role in MERGEABLE_FIELD_ROLES
            ],
            "merged": {
                "roles": list(MERGEABLE_FIELD_ROLES),
                "label": "施工员 + 测量员（合并岗位）",
            },
            "rule": "按工程情况可分开登记，也可由同一账号承担测量与施工两个岗位；不复制历史成果。",
        }

    def _require_pm(self, actor: dict[str, Any]) -> None:
        if actor.get("role") != ROLE_PROJECT_MANAGER or "authorize_personnel_admin" not in set(actor.get("permissions", [])):
            raise PersonnelPolicyError("只有项目经理可以授权行政人员管理人员")

    def authorize_personnel_admin(
        self,
        actor: dict[str, Any],
        user_id: str,
        authorized: bool = True,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_pm(actor)
        users = self._load()
        target = next((user for user in users if user.get("id") == str(user_id)), None)
        if target is None:
            raise ValueError("目标人员不存在")
        if project_id and not self._project_has_user(project_id, user_id):
            raise ValueError("目标行政人员不在当前项目名册")
        if target.get("role") != ROLE_ADMINISTRATIVE_OFFICER:
            raise ValueError("只有行政人员可以获得人员管理授权")
        grants = self._load_personnel_grants()
        if authorized:
            grants.add(str(user_id))
            action = "personnel.admin_authorized"
        else:
            grants.discard(str(user_id))
            action = "personnel.admin_revoked"
        self._save_personnel_grants(grants)
        self.record_personnel_audit(
            dict(actor),
            action,
            str(user_id),
            {"username": target.get("username", ""), "authorized": authorized},
            project_id=project_id,
        )
        return self.personnel_snapshot(project_id)

    def delete_user(self, actor: dict[str, Any], user_id: str, project_id: str | None = None) -> dict[str, Any]:
        if "manage_personnel" not in set(actor.get("permissions", [])):
            raise PersonnelPolicyError("当前角色没有人员管理权限")
        user_id = str(user_id)
        if user_id == str(actor.get("id", "")):
            raise PersonnelPolicyError("不能删除当前登录账号")
        if project_id:
            users = self._load()
            target = next((user for user in users if user.get("id") == user_id), None)
            if target is None:
                raise ValueError("目标人员不存在")
            self.remove_user_from_project(project_id, user_id)
            self.record_personnel_audit(
                dict(actor),
                "personnel.removed_from_project",
                user_id,
                {"username": target.get("username", ""), "role": target.get("role", ""), "project_id": project_id},
                project_id=project_id,
            )
            return self.personnel_snapshot(project_id)
        users = self._load()
        target = next((user for user in users if user.get("id") == user_id), None)
        if target is None:
            raise ValueError("目标人员不存在")
        if target.get("role") == ROLE_PROJECT_MANAGER and sum(item.get("role") == ROLE_PROJECT_MANAGER for item in users) <= 1:
            raise PersonnelPolicyError("至少保留一名项目经理")
        self._save([user for user in users if user.get("id") != user_id])
        grants = self._load_personnel_grants()
        grants.discard(user_id)
        self._save_personnel_grants(grants)
        self.record_personnel_audit(dict(actor), "personnel.deleted", user_id, {"username": target.get("username", ""), "role": target.get("role", "")})
        return self.personnel_snapshot()

    def rename_user(
        self,
        actor: dict[str, Any],
        user_id: str,
        new_username: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if "manage_personnel" not in set(actor.get("permissions", [])):
            raise PersonnelPolicyError("当前角色没有人员管理权限")
        new_username = str(new_username or "").strip()
        if len(new_username) < 1 or len(new_username) > 64:
            raise ValueError("姓名/登录名需要是 1 到 64 个字符")
        user_id = str(user_id)
        users = self._load()
        target = next((user for user in users if str(user.get("id")) == user_id), None)
        if target is None:
            raise ValueError("目标人员不存在")
        if project_id and not self._project_has_user(project_id, user_id):
            raise ValueError("目标人员不在当前项目名册")
        old_username = str(target.get("username", ""))
        if old_username.casefold() == new_username.casefold():
            raise ValueError("新姓名/登录名与当前相同")
        if any(str(user.get("username", "")).casefold() == new_username.casefold() for user in users if str(user.get("id")) != user_id):
            raise ValueError("该姓名/登录名已被其他人员使用")
        target["username"] = new_username
        target["display_name"] = new_username
        target.setdefault("name_history", []).append({
            "username": old_username,
            "changed_at": _now(),
            "changed_by": actor.get("id", ""),
        })
        self._save(users)
        self.record_personnel_audit(
            dict(actor),
            "personnel.renamed",
            user_id,
            {"old_username": old_username, "new_username": new_username, "role": target.get("role", "")},
            project_id=project_id,
        )
        return self.personnel_snapshot(project_id)

    def update_roles(
        self,
        actor: dict[str, Any],
        user_id: str,
        roles: list[str] | tuple[str, ...],
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if "manage_personnel" not in set(actor.get("permissions", [])):
            raise PersonnelPolicyError("当前角色没有人员管理权限")
        user_id = str(user_id)
        users = self._load()
        target = next((user for user in users if str(user.get("id")) == user_id), None)
        if target is None:
            raise ValueError("目标人员不存在")
        if project_id and not self._project_has_user(project_id, user_id):
            raise ValueError("目标人员不在当前项目名册")
        primary = _normalize_role(str(target.get("role", "")))
        assigned_roles = _normalize_roles(roles, primary)
        old_roles = _normalize_roles(target.get("roles"), primary)
        if old_roles == assigned_roles:
            raise ValueError("岗位组合没有变化")
        target["roles"] = assigned_roles
        self._save(users)
        self.record_personnel_audit(
            dict(actor),
            "personnel.roles_changed",
            user_id,
            {"username": target.get("username", ""), "old_roles": old_roles, "new_roles": assigned_roles},
            project_id=project_id,
        )
        return self.personnel_snapshot(project_id)

    def record_personnel_audit(
        self,
        actor: dict[str, Any],
        action: str,
        target: str,
        details: dict[str, Any] | None = None,
        project_id: str | None = None,
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
        if project_id:
            audits = self._load_project_personnel_audit()
            audits.setdefault(str(project_id), []).append(event)
            audits[str(project_id)] = audits[str(project_id)][-500:]
            self._save_project_personnel_audit(audits)
        return event

    def personnel_snapshot(self, project_id: str | None = None) -> dict[str, Any]:
        member_ids = None
        audit_log = self._load_personnel_audit()
        if project_id:
            project_id = str(project_id).strip()
            member_ids = set(self.ensure_project_membership(project_id))
            audit_log = self._load_project_personnel_audit().get(project_id, [])
        users = self.list_public_users()
        if member_ids is not None:
            users = [user for user in users if str(user.get("id")) in member_ids]
        return {
            "project_id": project_id or "",
            "users": users,
            "audit_log": audit_log,
            "roles": self.personnel_role_catalog(),
            "assignment_catalog": self.personnel_assignment_catalog(),
            "policy": {
                "direct_manager_roles": [ROLE_PROJECT_MANAGER],
                "delegated_manager_role": ROLE_ADMINISTRATIVE_OFFICER,
                "authorization": "行政人员必须由项目经理明确授权后才能增减人员",
                "handover": "更换姓名只更新登录名和显示名，保留 user_id、密码、岗位、审计和项目成果；新姓名可直接接管原账号。",
                "project_scope": "每个项目拥有独立人员名册；在一个项目增删人员不会改变其他项目的人员名册。",
            },
        }
