from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.auth import LocalAuthStore


class LocalAuthTests(unittest.TestCase):
    def test_passwords_are_stored_as_hashes_and_roles_have_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAuthStore(Path(directory))
            user = store.register("manager", "secret1", "project_manager")
            self.assertEqual(user["role"], "project_manager")
            self.assertIn("delete_source", user["permissions"])
            raw = (Path(directory) / "users.json").read_text(encoding="utf-8")
            self.assertNotIn("secret1", raw)
            self.assertEqual(store.authenticate("manager", "secret1")["id"], user["id"])
            with self.assertRaises(ValueError):
                store.authenticate("manager", "wrong-pass")

