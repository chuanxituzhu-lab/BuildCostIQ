from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from adapters.deployment import DeploymentConfig, DeploymentStorageAdapter, StorageRoots
from adapters.workspace import LocalProjectWorkspace
from core.execution_ledger import EVENT_TYPES, ExecutionLedgerError, verify_execution_chain


class ExecutionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        roots = StorageRoots.from_environment({"BUILDCOSTIQ_DATA_ROOT": str(root / "data")})
        config = DeploymentConfig(mode="single-node", node_id="test", host="127.0.0.1", port=8787, roots=roots)
        self.storage = DeploymentStorageAdapter(config)
        self.workspace = LocalProjectWorkspace(roots.projects, storage_adapter=self.storage)
        self.workspace.create("project-a", "合成项目")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _fields(self, *, key: str = "event-1", summary: str = "形成计划记录", **updates):
        fields = {
            "run_id": "run-1",
            "workflow_id": "WF02",
            "module_id": "02",
            "event_type": "RUN_CREATED",
            "actor_type": "human",
            "actor_id": "user-test",
            "target_type": "run",
            "target_id": "run-1",
            "payload_summary": summary,
            "evidence_refs": [],
            "result_version_refs": [],
            "checkpoint_ref": "",
            "idempotency_key": key,
            "data_classification": "Restricted",
        }
        fields.update(updates)
        return fields

    def test_events_are_hash_linked_and_project_scoped(self) -> None:
        first = self.workspace.append_execution_event("project-a", self._fields())
        second = self.workspace.append_execution_event(
            "project-a",
            self._fields(key="event-2", event_type="RESULT_CREATED", target_type="result", target_id="result-1:v1"),
        )
        self.assertEqual(first["event_hash"], second["previous_event_hash"])
        self.assertEqual("project-a", second["project_id"])
        self.assertEqual(2, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_tampering_is_detected_before_further_use(self) -> None:
        self.workspace.append_execution_event("project-a", self._fields())
        state = self.workspace.load("project-a")
        state["execution_ledger"][0]["payload_summary"] = "被改写的摘要"
        self.workspace.save(state)
        with self.assertRaisesRegex(ExecutionLedgerError, "哈希校验失败"):
            self.workspace.verify_execution_ledger("project-a")
        with self.assertRaises(ExecutionLedgerError):
            self.workspace.append_execution_event("project-a", self._fields(key="event-2"))

    def test_idempotent_retry_returns_original_and_conflicting_retry_fails(self) -> None:
        original = self.workspace.append_execution_event("project-a", self._fields())
        retry = self.workspace.append_execution_event("project-a", self._fields())
        self.assertEqual(original["event_id"], retry["event_id"])
        self.assertEqual(1, self.workspace.verify_execution_ledger("project-a")["event_count"])
        with self.assertRaisesRegex(ExecutionLedgerError, "不同运行事件"):
            self.workspace.append_execution_event("project-a", self._fields(summary="不同内容"))

    def test_agent_ops_ready_is_recorded_as_plan_only(self) -> None:
        event = self.workspace.append_execution_event(
            "project-a",
            self._fields(
                event_type="AGENT_OPS_PLAN_RECORDED",
                agent_ops_state="READY",
                actor_type="agent",
                actor_id="sayelf-agent-ops",
                payload_summary="任务计划已就绪",
            ),
        )
        self.assertEqual("READY", event["agent_ops_state"])
        self.assertEqual("plan_ready_only", event["agent_ops_state_meaning"])
        self.assertEqual("candidate", event["record_authority"])
        self.assertNotIn("RUN_COMPLETED", EVENT_TYPES)
        self.assertTrue(self.workspace.verify_execution_ledger("project-a")["valid"])

    def test_plan_state_projection_uses_latest_event_without_erasing_history(self) -> None:
        for index, plan_state in enumerate(("INBOX", "WORKING", "READY"), start=1):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key=f"plan-r1-{index}",
                    run_id="run-1",
                    event_type="AGENT_OPS_PLAN_RECORDED",
                    actor_type="agent",
                    actor_id="local-planner",
                    target_type="workflow_plan",
                    target_id="bid-preparation",
                    payload_summary=f"计划状态更新为 {plan_state}",
                    agent_ops_state=plan_state,
                ),
            )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="plan-r2-1",
                run_id="run-2",
                workflow_id="WF04",
                module_id="04",
                event_type="AGENT_OPS_PLAN_RECORDED",
                actor_type="agent",
                actor_id="local-planner",
                target_type="workflow_plan",
                target_id="construction-cost",
                payload_summary="计划已分解",
                agent_ops_state="SCOPED",
            ),
        )

        snapshot = self.workspace.execution_ledger_snapshot("project-a")
        self.assertEqual(4, snapshot["event_count"])
        self.assertEqual(["run-1", "run-2"], [item["run_id"] for item in snapshot["agent_ops_plan_states"]])
        first, second = snapshot["agent_ops_plan_states"]
        self.assertEqual("READY", first["state"])
        self.assertEqual("plan_ready_only", first["state_meaning"])
        self.assertEqual("SCOPED", second["state"])

    def test_plan_state_projection_omits_runs_without_plan_events(self) -> None:
        self.workspace.append_execution_event("project-a", self._fields(event_type="RUN_CREATED"))
        self.assertEqual([], self.workspace.execution_ledger_snapshot("project-a")["agent_ops_plan_states"])

    def test_project_scope_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExecutionLedgerError, "项目范围"):
            self.workspace.append_execution_event("project-a", self._fields(project_id="project-b"))

    def test_evidence_refs_must_resolve_to_active_sources_in_this_project(self) -> None:
        digest = "a" * 64
        self.workspace.add_source("project-a", {"source_id": "source-a", "content_hash": digest, "status": "active"})
        event = self.workspace.append_execution_event(
            "project-a",
            self._fields(evidence_refs=[f"sha256:{digest}"]),
        )
        self.assertEqual([f"sha256:{digest}"], event["evidence_refs"])

        with self.assertRaisesRegex(ExecutionLedgerError, "当前有效来源"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key="unknown-source", evidence_refs=[f"sha256:{'b' * 64}"]),
            )
        with self.assertRaisesRegex(ExecutionLedgerError, "当前有效来源"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key="source-id-is-not-a-content-ref", evidence_refs=["source-a"]),
            )
        self.assertEqual(1, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_evidence_refs_reject_other_project_and_soft_deleted_sources(self) -> None:
        self.workspace.create("project-b", "另一个合成项目")
        other_digest = "c" * 64
        self.workspace.add_source("project-b", {"source_id": "source-b", "content_hash": other_digest, "status": "active"})
        with self.assertRaisesRegex(ExecutionLedgerError, "当前有效来源"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(evidence_refs=[f"sha256:{other_digest}"]),
            )

        deleted_digest = "d" * 64
        self.workspace.add_source("project-a", {"source_id": "source-deleted", "content_hash": deleted_digest, "status": "active"})
        self.workspace.soft_delete_source("project-a", "source-deleted", "test-user")
        with self.assertRaisesRegex(ExecutionLedgerError, "当前有效来源"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key="deleted-source", evidence_refs=[f"sha256:{deleted_digest}"]),
            )
        self.assertEqual(0, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_result_version_refs_require_an_earlier_version_event_in_this_project(self) -> None:
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="version-register",
                event_type="RESULT_VERSIONED",
                target_type="result_version",
                target_id="boq-result-v1",
            ),
        )
        event = self.workspace.append_execution_event(
            "project-a",
            self._fields(key="version-consumer", result_version_refs=["result-version:boq-result-v1"]),
        )
        self.assertEqual(["result-version:boq-result-v1"], event["result_version_refs"])

        with self.assertRaisesRegex(ExecutionLedgerError, "更早登记"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key="unknown-version", result_version_refs=["result-version:boq-result-v2"]),
            )
        self.workspace.create("project-b", "另一个合成项目")
        self.workspace.append_execution_event(
            "project-b",
            self._fields(
                key="foreign-version",
                event_type="RESULT_VERSIONED",
                target_type="result_version",
                target_id="foreign-result-v1",
            ),
        )
        with self.assertRaisesRegex(ExecutionLedgerError, "更早登记"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key="foreign-version-reference", result_version_refs=["result-version:foreign-result-v1"]),
            )
        self.assertEqual(2, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_checkpoint_recovery_sequence_requires_prior_same_run_checkpoint(self) -> None:
        checkpoint = self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="checkpoint-1",
                event_type="CHECKPOINT_CREATED",
                target_type="checkpoint",
                target_id="cp-1",
                payload_summary="已记录候选检查点",
            ),
        )
        self.assertEqual("cp-1", checkpoint["target_id"])
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="recovery-start-1",
                event_type="RECOVERY_STARTED",
                target_type="checkpoint",
                target_id="cp-1",
                checkpoint_ref="checkpoint:cp-1",
                payload_summary="开始恢复处理",
            ),
        )
        completed = self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="recovery-complete-1",
                event_type="RECOVERY_COMPLETED",
                target_type="checkpoint",
                target_id="cp-1",
                checkpoint_ref="checkpoint:cp-1",
                payload_summary="恢复处理记录结束",
            ),
        )
        self.assertEqual("candidate", completed["record_authority"])
        self.assertEqual(3, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_checkpoint_recovery_rejects_unknown_duplicate_and_unmatched_events(self) -> None:
        with self.assertRaisesRegex(ExecutionLedgerError, "更早登记的检查点"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="unknown-checkpoint",
                    event_type="RECOVERY_STARTED",
                    target_type="checkpoint",
                    target_id="cp-missing",
                    checkpoint_ref="checkpoint:cp-missing",
                    payload_summary="不得使用未知检查点",
                ),
            )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="checkpoint-1",
                event_type="CHECKPOINT_CREATED",
                target_type="checkpoint",
                target_id="cp-1",
                payload_summary="登记检查点",
            ),
        )
        with self.assertRaisesRegex(ExecutionLedgerError, "缺少同一检查点"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="orphan-completion",
                    event_type="RECOVERY_COMPLETED",
                    target_type="checkpoint",
                    target_id="cp-1",
                    checkpoint_ref="checkpoint:cp-1",
                    payload_summary="不得记录孤立完成",
                ),
            )
        with self.assertRaisesRegex(ExecutionLedgerError, "编号不能重复"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="duplicate-checkpoint",
                    event_type="CHECKPOINT_CREATED",
                    target_type="checkpoint",
                    target_id="cp-1",
                    payload_summary="重复编号",
                ),
            )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="recovery-start-1",
                event_type="RECOVERY_STARTED",
                target_type="checkpoint",
                target_id="cp-1",
                checkpoint_ref="checkpoint:cp-1",
                payload_summary="开始恢复",
            ),
        )
        with self.assertRaisesRegex(ExecutionLedgerError, "未结束的恢复尝试"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="recovery-start-duplicate",
                    event_type="RECOVERY_STARTED",
                    target_type="checkpoint",
                    target_id="cp-1",
                    checkpoint_ref="checkpoint:cp-1",
                    payload_summary="不得重复开启恢复",
                ),
            )
        self.assertEqual(2, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_checkpoint_reference_cannot_cross_runs(self) -> None:
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="checkpoint-other-run",
                run_id="run-2",
                event_type="CHECKPOINT_CREATED",
                target_type="checkpoint",
                target_id="cp-foreign-run",
                payload_summary="另一运行的检查点",
            ),
        )
        with self.assertRaisesRegex(ExecutionLedgerError, "更早登记的检查点"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="recovery-cross-run",
                    run_id="run-1",
                    event_type="RECOVERY_STARTED",
                    target_type="checkpoint",
                    target_id="cp-foreign-run",
                    checkpoint_ref="checkpoint:cp-foreign-run",
                    payload_summary="不得引用其他运行检查点",
                ),
            )
        self.assertEqual(1, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_failure_can_close_a_recovery_attempt_before_retry(self) -> None:
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="checkpoint-1",
                event_type="CHECKPOINT_CREATED",
                target_type="checkpoint",
                target_id="cp-1",
                payload_summary="登记检查点",
            ),
        )
        common = {
            "target_type": "checkpoint",
            "target_id": "cp-1",
            "checkpoint_ref": "checkpoint:cp-1",
        }
        self.workspace.append_execution_event(
            "project-a",
            self._fields(key="recovery-start-1", event_type="RECOVERY_STARTED", payload_summary="开始恢复", **common),
        )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(key="recovery-failed-1", event_type="FAILURE_RECORDED", payload_summary="恢复尝试失败", **common),
        )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(key="recovery-start-2", event_type="RECOVERY_STARTED", payload_summary="重试恢复", **common),
        )
        self.workspace.append_execution_event(
            "project-a",
            self._fields(key="recovery-complete-2", event_type="RECOVERY_COMPLETED", payload_summary="恢复记录结束", **common),
        )
        self.assertEqual(5, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_handoff_requires_same_run_creation_and_single_consumption(self) -> None:
        with self.assertRaisesRegex(ExecutionLedgerError, "更早创建的交接"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="handoff-orphan",
                    event_type="HANDOFF_CONSUMED",
                    target_type="handoff",
                    target_id="handoff-1",
                    payload_summary="不得接收未知交接",
                ),
            )
        created = self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="handoff-create",
                event_type="HANDOFF_CREATED",
                target_type="handoff",
                target_id="handoff-1",
                payload_summary="记录候选岗位交接",
            ),
        )
        self.assertEqual("candidate", created["record_authority"])
        with self.assertRaisesRegex(ExecutionLedgerError, "不能重复创建"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="handoff-create-duplicate",
                    event_type="HANDOFF_CREATED",
                    target_type="handoff",
                    target_id="handoff-1",
                    payload_summary="不得重复创建交接编号",
                ),
            )
        consumed = self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="handoff-consume",
                event_type="HANDOFF_CONSUMED",
                target_type="handoff",
                target_id="handoff-1",
                payload_summary="记录一次交接接收",
            ),
        )
        self.assertEqual("handoff-1", consumed["target_id"])
        with self.assertRaisesRegex(ExecutionLedgerError, "只能记录一次接收"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="handoff-consume-duplicate",
                    event_type="HANDOFF_CONSUMED",
                    target_type="handoff",
                    target_id="handoff-1",
                    payload_summary="不得重复接收交接",
                ),
            )
        self.assertEqual(2, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_handoff_cannot_be_consumed_from_another_run(self) -> None:
        self.workspace.append_execution_event(
            "project-a",
            self._fields(
                key="handoff-create-other-run",
                run_id="run-2",
                event_type="HANDOFF_CREATED",
                target_type="handoff",
                target_id="handoff-foreign-run",
                payload_summary="另一运行创建交接",
            ),
        )
        with self.assertRaisesRegex(ExecutionLedgerError, "更早创建的交接"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(
                    key="handoff-consume-cross-run",
                    run_id="run-1",
                    event_type="HANDOFF_CONSUMED",
                    target_type="handoff",
                    target_id="handoff-foreign-run",
                    payload_summary="不得跨运行接收交接",
                ),
            )
        self.assertEqual(1, self.workspace.verify_execution_ledger("project-a")["event_count"])

    def test_ledger_cannot_record_canonical_promotion(self) -> None:
        with self.assertRaisesRegex(ExecutionLedgerError, "事件类型不受支持"):
            self.workspace.append_execution_event(
                "project-a",
                self._fields(event_type="CANONICAL_PROMOTED"),
            )

    def test_concurrent_appends_preserve_one_valid_hash_chain(self) -> None:
        def append(index: int) -> None:
            self.workspace.append_execution_event(
                "project-a",
                self._fields(key=f"parallel-{index}", target_id=f"run-{index}"),
            )

        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(append, range(18)))
        state = self.workspace.load("project-a")
        self.assertEqual(18, len(state["execution_ledger"]))
        self.assertEqual(18, len({item["event_hash"] for item in state["execution_ledger"]}))
        self.assertEqual(18, self.workspace.verify_execution_ledger("project-a")["event_count"])
        self.assertEqual(state["execution_ledger"][-1]["event_hash"], verify_execution_chain(state["execution_ledger"], "project-a"))


if __name__ == "__main__":
    unittest.main()
