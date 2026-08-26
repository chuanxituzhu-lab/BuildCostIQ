import unittest
from unittest.mock import patch

from core import CapabilityGateway, Runtime, current_version, normalize_version
from plugins import build_default_plugins


class CoreTests(unittest.TestCase):
    def test_default_runtime_exposes_p01_to_p09(self):
        runtime = Runtime(build_default_plugins())
        self.assertEqual(runtime.gateway.registered, tuple(f"P{i:02d}" for i in range(1, 10)))
        self.assertEqual(runtime.health()["version"], "0.8.0-rc9")

    def test_p10_is_rejected(self):
        class P10:
            capability_id = "P10"
            def execute(self, context):
                return context

        with self.assertRaises(ValueError):
            CapabilityGateway().register(P10())

    def test_context_validation(self):
        runtime = Runtime(build_default_plugins())
        with self.assertRaises(ValueError):
            runtime.gateway.execute("P01", {"project_id": "demo"})

    def test_runtime_version_is_single_source_and_supports_release_override(self):
        self.assertEqual(Runtime().health()["version"], current_version())
        self.assertEqual(normalize_version("v0.8.0rc5"), "0.8.0-rc5")
        with patch.dict("os.environ", {"BUILDCOSTIQ_VERSION": "v9.1.0-rc4"}):
            self.assertEqual(Runtime().health()["version"], "9.1.0-rc4")


if __name__ == "__main__":
    unittest.main()

