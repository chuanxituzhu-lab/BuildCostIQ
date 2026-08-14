from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.auth import LocalAuthStore


class LocalAuthTests(unittest.TestCase):
    def test_passwords_are_stored_as_hashes_and_roles_have_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAuthStore(Path(directory))
            user = store.register("manager", "secret1", "cost_manager")
            self.assertEqual(user["role"], "cost_manager")
            self.assertIn("delete_source", user["permissions"])
            self.assertTrue(user["can_view_cost_detail"])
            raw = (Path(directory) / "users.json").read_text(encoding="utf-8")
            self.assertNotIn("secret1", raw)
            self.assertEqual(store.authenticate("manager", "secret1")["id"], user["id"])
            with self.assertRaises(ValueError):
                store.authenticate("manager", "wrong-pass")

            project_manager = store.register("project-manager", "secret1", "project_manager")
            self.assertEqual(project_manager["role_level"], 1)
            self.assertNotIn("delete_source", project_manager["permissions"])
            self.assertFalse(project_manager["can_view_cost_detail"])

            estimator = store.register("estimator", "secret1", "cost_estimator")
            self.assertEqual(estimator["role_level"], 2)
            self.assertIn("edit_business_data", estimator["permissions"])
            self.assertNotIn("view_cost_detail", estimator["permissions"])
