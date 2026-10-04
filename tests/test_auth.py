from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.auth import LocalAuthStore, PERMISSION_LABELS, ROLE_PERMISSIONS


class LocalAuthTests(unittest.TestCase):
    def test_password_minimum_is_eight_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAuthStore(Path(directory))
            with self.assertRaisesRegex(ValueError, "至少需要 8 位"):
                store.register("short-password", "short77", "project_manager")
            user = store.register("eight-character", "Smoke@12", "project_manager")
            self.assertEqual(store.authenticate("eight-character", "Smoke@12")["id"], user["id"])

    def test_passwords_are_stored_as_hashes_and_roles_have_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAuthStore(Path(directory))
            user = store.register("manager", "secret12", "cost_manager")
            self.assertEqual(user["role"], "cost_manager")
            self.assertIn("delete_source", user["permissions"])
            self.assertTrue(user["can_view_cost_detail"])
            self.assertNotIn("manage_personnel", user["permissions"])
            raw = (Path(directory) / "users.json").read_text(encoding="utf-8")
            self.assertNotIn("secret12", raw)
            self.assertEqual(store.authenticate("manager", "secret12")["id"], user["id"])
            with self.assertRaises(ValueError):
                store.authenticate("manager", "wrong-pass")

            project_manager = store.register("project-manager", "secret12", "project_manager")
            self.assertEqual(project_manager["role_level"], 1)
            self.assertNotIn("delete_source", project_manager["permissions"])
            self.assertIn("manage_personnel", project_manager["permissions"])
            self.assertFalse(project_manager["can_view_cost_detail"])

            estimator = store.register("estimator", "secret12", "cost_estimator")
            self.assertEqual(estimator["role_level"], 2)
            self.assertIn("edit_business_data", estimator["permissions"])
            self.assertNotIn("view_cost_detail", estimator["permissions"])
            self.assertNotIn("manage_personnel", estimator["permissions"])

            administrative = store.register("administrative", "secret12", "administrative_officer")
            self.assertNotIn("manage_personnel", administrative["permissions"])
            self.assertFalse(administrative["personnel_admin_authorized"])
            with self.assertRaises(PermissionError):
                store.authorize_personnel_admin(user, administrative["id"])
            store.authorize_personnel_admin(project_manager, administrative["id"])
            authorized_admin = next(item for item in store.list_public_users() if item["id"] == administrative["id"])
            self.assertIn("manage_personnel", authorized_admin["permissions"])
            self.assertTrue(authorized_admin["personnel_admin_authorized"])
            snapshot = store.personnel_snapshot()
            self.assertEqual(len(snapshot["roles"]), 14)
            self.assertEqual(snapshot["policy"]["delegated_manager_role"], "administrative_officer")
            self.assertEqual(snapshot["assignment_catalog"]["merged"]["roles"], ["surveyor", "site_engineer"])
            self.assertEqual(set().union(*ROLE_PERMISSIONS.values()), set(PERMISSION_LABELS))
            for role_entry in snapshot["roles"]:
                expected_permissions = ROLE_PERMISSIONS[role_entry["role"]]
                self.assertEqual(expected_permissions, {item["key"] for item in role_entry["permissions"]})
                self.assertTrue(all(item["label"] for item in role_entry["permissions"]))
            self.assertEqual(
                "lab_testing_officer",
                store.register("试验岗位别名", "secret12", "实验员")["role"],
            )

            public_users = store.list_public_users()
            self.assertEqual(len(public_users), 5)
            self.assertTrue(all("password" not in user for user in public_users))

    def test_personnel_handover_preserves_account_identity_and_supports_merged_field_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAuthStore(Path(directory))
            manager = store.register("manager", "secret12", "project_manager")
            surveyor = store.register("甲", "secret12", "surveyor")
            original_id = surveyor["id"]
            original_created_at = surveyor["created_at"]

            store.update_roles(manager, original_id, ["surveyor", "site_engineer"])
            merged = next(item for item in store.list_public_users() if item["id"] == original_id)
            self.assertEqual(merged["role_assignment"], "merged")
            self.assertEqual(set(merged["roles"]), {"surveyor", "site_engineer"})

            store.rename_user(manager, original_id, "乙")
            handed_over = store.authenticate("乙", "secret12")
            self.assertEqual(handed_over["id"], original_id)
            self.assertEqual(handed_over["created_at"], original_created_at)
            self.assertEqual(handed_over["role_assignment"], "merged")
            with self.assertRaises(ValueError):
                store.authenticate("甲", "secret12")
            history = handed_over.get("name_history", [])
            self.assertEqual(history[0]["username"], "甲")
            audit_actions = [item["action"] for item in store.personnel_snapshot()["audit_log"]]
            self.assertIn("personnel.renamed", audit_actions)
            self.assertIn("personnel.roles_changed", audit_actions)
