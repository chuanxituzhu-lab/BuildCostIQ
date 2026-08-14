import unittest

from core import CapabilityGateway, Runtime
from plugins import build_default_plugins


class CoreTests(unittest.TestCase):
    def test_default_runtime_exposes_exactly_p01_to_p08(self):
        runtime = Runtime(build_default_plugins())
        self.assertEqual(runtime.gateway.registered, tuple(f"P{i:02d}" for i in range(1, 9)))
        self.assertEqual(runtime.health()["version"], "0.7.2-rc8")

    def test_p09_is_rejected(self):
        class P09:
            capability_id = "P09"
            def execute(self, context):
                return context

        with self.assertRaises(ValueError):
            CapabilityGateway().register(P09())

    def test_context_validation(self):
        runtime = Runtime(build_default_plugins())
        with self.assertRaises(ValueError):
            runtime.gateway.execute("P01", {"project_id": "demo"})


if __name__ == "__main__":
    unittest.main()

