from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from adapters.deployment import DeploymentConfig, DeploymentStorageAdapter, StorageRoots
from adapters.workspace import LocalProjectWorkspace


class DeploymentStorageTests(unittest.TestCase):
    def test_environment_config_binds_one_data_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "BuildCostIQData"
            config = DeploymentConfig(
                mode="central",
                node_id="project-server-01",
                host="0.0.0.0",
                port=8787,
                roots=StorageRoots(
                    data_root=root,
                    projects=root / "projects",
                    sources=root / "sources",
                    archive=root / "archive",
                    basis=root / "basis",
                    auth=root / "auth",
                    backups=root / "backups",
                    locks=root / "locks",
                ),
            )
            adapter = DeploymentStorageAdapter(config)
            workspace = LocalProjectWorkspace(config.roots.projects, storage_adapter=adapter)
            created = workspace.create("municipal-001", "市政示例项目")
            self.assertEqual(created["project"]["revision"], 1)
            self.assertTrue(config.roots.projects.exists())
            self.assertTrue(config.roots.locks.exists())
            public = config.public()
            self.assertTrue(public["authoritative"])
            self.assertFalse(public["consistency"]["direct_shared_folder_writes"])
            self.assertEqual(public["storage"]["project_state"], "projects")

    def test_project_writes_are_serialized_and_revisioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = DeploymentConfig(
                mode="central",
                node_id="test-node",
                host="127.0.0.1",
                port=0,
                roots=StorageRoots(root, root / "projects", root / "sources", root / "archive", root / "basis", root / "auth", root / "backups", root / "locks"),
            )
            adapter = DeploymentStorageAdapter(config)
            workspace = LocalProjectWorkspace(config.roots.projects, storage_adapter=adapter)
            workspace.create("municipal-002", "并发写入测试")

            def write_stage(index: int) -> None:
                workspace.set_stage("municipal-002", f"stage_{index}", {"index": index})

            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(write_stage, range(8)))

            state = workspace.load("municipal-002")
            assert state is not None
            self.assertEqual(state["project"]["revision"], 9)
            self.assertEqual(len([key for key in state if key.startswith("stage_")]), 8)
            json.loads((config.roots.projects / "municipal-002.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
