import unittest

from core import Runtime
from plugins import build_default_plugins


class WorkflowTests(unittest.TestCase):
    def test_demo_project_traverses_frozen_capabilities(self):
        runtime = Runtime(build_default_plugins())
        context = {"project_id": "demo-project", "source_id": "sanitized-source"}
        results = [runtime.gateway.execute(capability_id, context) for capability_id in runtime.gateway.registered]
        self.assertEqual([result["status"] for result in results], ["accepted"] * 8)
        self.assertEqual([result["capability_id"] for result in results], list(runtime.gateway.registered))


if __name__ == "__main__":
    unittest.main()

