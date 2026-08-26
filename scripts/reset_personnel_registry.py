"""Archive the old local personnel registry and seed the current role roster.

This is an explicit local maintenance action, not part of the web request path.
It keeps a timestamped copy of the previous registry and audit log before
replacing the active list.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from adapters.auth import LocalAuthStore


INITIAL_PASSWORD = "BuildCostIQ2026!"
BASE_PERSONNEL = (
    ("项目经理01", "project_manager"),
    ("造价经理01", "cost_manager"),
    ("造价员01", "cost_estimator"),
    ("技术负责人01", "technical_lead"),
    ("生产经理01", "production_manager"),
    ("施工员/测量员01", "site_engineer"),
    ("测量员01", "surveyor"),
    ("质量负责人01", "quality_officer"),
    ("试验检测员01", "lab_testing_officer"),
    ("资料员01", "document_controller"),
    ("安全员01", "safety_officer"),
    ("采购员01", "procurement_officer"),
    ("仓管员01", "warehouse_officer"),
    ("行政人员01", "administrative_officer"),
)


def reset(root: Path | str | None = None) -> dict[str, object]:
    root = root or (Path(__file__).resolve().parents[1] / "runtime" / "auth")
    auth_root = Path(root)
    auth_root.mkdir(parents=True, exist_ok=True)
    users_path = auth_root / "users.json"
    audit_path = auth_root / "personnel_audit.json"
    grants_path = auth_root / "personnel_grants.json"
    memberships_path = auth_root / "project_memberships.json"
    project_audit_path = auth_root / "project_personnel_audit.json"
    basic_ids_path = auth_root / "basic_personnel_ids.json"
    old_users = json.loads(users_path.read_text(encoding="utf-8")) if users_path.exists() else []
    old_audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = auth_root / "archive" / f"personnel-reset-{stamp}"
    archive.mkdir(parents=True, exist_ok=False)
    if users_path.exists():
        shutil.copy2(users_path, archive / "users-before-reset.json")
    if audit_path.exists():
        shutil.copy2(audit_path, archive / "personnel-audit-before-reset.json")
    if grants_path.exists():
        shutil.copy2(grants_path, archive / "personnel-grants-before-reset.json")
    if memberships_path.exists():
        shutil.copy2(memberships_path, archive / "project-memberships-before-reset.json")
    if project_audit_path.exists():
        shutil.copy2(project_audit_path, archive / "project-personnel-audit-before-reset.json")
    if basic_ids_path.exists():
        shutil.copy2(basic_ids_path, archive / "basic-personnel-ids-before-reset.json")

    store = LocalAuthStore(auth_root)
    store._save([])
    store._save_personnel_grants(set())
    store._save_project_memberships({})
    store._save_project_personnel_audit({})
    store._save_basic_personnel_ids(set())
    seeded = [store.register(username, INITIAL_PASSWORD, role) for username, role in BASE_PERSONNEL]
    store._save_basic_personnel_ids({str(item["id"]) for item in seeded})
    store._save_personnel_audit([
        {
            "id": f"registry-reset-{stamp}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "personnel.registry_reset",
            "actor": {"id": "system", "username": "system-personnel-reset", "role": "system", "role_label": "系统维护"},
            "target": "personnel-registry",
            "details": {
                "previous_active_count": len(old_users) if isinstance(old_users, list) else 0,
                "previous_audit_count": len(old_audit) if isinstance(old_audit, list) else 0,
                "new_active_count": len(seeded),
                "archive": str(archive),
                "reason": "按当前项目岗位角色重置基础人员名册",
            },
        }
    ])
    return {
        "archive": str(archive),
        "previous_active_count": len(old_users) if isinstance(old_users, list) else 0,
        "previous_audit_count": len(old_audit) if isinstance(old_audit, list) else 0,
        "new_active_count": len(seeded),
        "project_memberships_reset": True,
        "users": [{"username": item["username"], "role": item["role"]} for item in seeded],
    }


if __name__ == "__main__":
    print(json.dumps(reset(), ensure_ascii=False, indent=2))
