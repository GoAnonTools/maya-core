import unittest
from tempfile import TemporaryDirectory

from app.delegation import (
    DelegationManager,
    DelegationRequest,
    ExecutionAuditStatus,
    ExecutionAuditStore,
    OptInHermesExecutorSelector,
)
from app.delegation.policy import HermesDelegationPolicy
from app.services.lightning_executor import (
    ExecutorCapabilities,
    InMemoryLightningExecutor,
)


class FakeHermesExecutor(InMemoryLightningExecutor):
    @property
    def backend_name(self):
        return "hermes"

    def capabilities(self):
        return ExecutorCapabilities(
            supported_task_categories=frozenset({"coding"}),
            available=True,
            version="fake-1",
            metadata={"provider": "hermes"},
        )


class DelegationAuditTests(unittest.TestCase):
    def request(self, delegation_id="audit-delegation", **metadata):
        return DelegationRequest(
            delegation_id=delegation_id,
            task="Implement a coding change",
            metadata={"task_category": "coding", **metadata},
        )

    def selector(self, hermes=None, enabled=True):
        return OptInHermesExecutorSelector(
            hermes_executor=hermes or FakeHermesExecutor(),
            fallback_executor=InMemoryLightningExecutor(),
            policy=HermesDelegationPolicy(enabled=enabled),
        )

    def test_fake_executor_records_full_lifecycle(self):
        manager = DelegationManager()

        manager.execute_with_executor(
            self.request(),
            selector=self.selector(),
        )

        record = manager.execution_record("audit-delegation")
        self.assertEqual(
            record.history,
            [
                ExecutionAuditStatus.CREATED,
                ExecutionAuditStatus.SELECTED,
                ExecutionAuditStatus.RUNNING,
                ExecutionAuditStatus.COMPLETED,
            ],
        )
        self.assertEqual(record.executor_selected, "hermes")
        self.assertEqual(record.terminal_status, "completed")
        self.assertIn("selected", record.timestamps)
        self.assertIn("completed", record.timestamps)

    def test_hermes_opt_in_trace_records_policy_and_capability_decision(self):
        manager = DelegationManager()

        manager.execute_with_executor(
            self.request(),
            selector=self.selector(enabled=True),
        )

        record = manager.execution_record("audit-delegation")
        self.assertEqual(record.policy_recommendation, "candidate")
        self.assertEqual(record.capability_decision["hermes_available"], True)
        self.assertEqual(record.capability_decision["hermes_capability_version"], "fake-1")

    def test_approval_wait_is_audited_without_submission(self):
        manager = DelegationManager()

        manager.execute_with_executor(
            self.request(requires_approval=True),
            selector=self.selector(),
        )

        record = manager.execution_record("audit-delegation")
        self.assertEqual(
            record.history,
            [
                ExecutionAuditStatus.CREATED,
                ExecutionAuditStatus.SELECTED,
                ExecutionAuditStatus.WAITING_APPROVAL,
            ],
        )
        self.assertEqual(record.approval_state, "pending")
        self.assertIsNone(record.terminal_status)

    def test_audit_records_recover_after_restart(self):
        with TemporaryDirectory() as directory:
            delegation_path = f"{directory}/delegations.json"
            audit_path = f"{directory}/execution-audit.json"
            first = DelegationManager(
                persistence_path=delegation_path,
                audit_path=audit_path,
            )
            first.execute_with_executor(
                self.request("audit-recovered"),
                selector=self.selector(),
            )

            recovered = DelegationManager(
                persistence_path=delegation_path,
                audit_path=audit_path,
            )
            record = recovered.execution_record("audit-recovered")

            self.assertEqual(record.executor_selected, "hermes")
            self.assertEqual(record.terminal_status, "completed")
            self.assertEqual(record.history[-1], ExecutionAuditStatus.COMPLETED)

    def test_audit_store_can_be_injected(self):
        store = ExecutionAuditStore()
        manager = DelegationManager(audit_store=store)
        manager.accept(self.request())

        self.assertIs(manager.execution_record("audit-delegation"), store.get("audit-delegation"))


if __name__ == "__main__":
    unittest.main()
