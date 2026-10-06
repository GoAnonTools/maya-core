import unittest
from tempfile import TemporaryDirectory

from app.delegation import (
    DelegationManager,
    DelegationRequest,
    ExecutionAuditStatus,
)


class DelegationObservabilityTests(unittest.TestCase):
    def request(self, delegation_id="observability-delegation"):
        return DelegationRequest(
            delegation_id=delegation_id,
            task="Analyze a repository",
        )

    def test_timeline_and_operator_summary(self):
        manager = DelegationManager()
        manager.accept(self.request())
        manager.start("observability-delegation", message="Execution started")
        manager.progress(
            "observability-delegation",
            0.5,
            message="Halfway through analysis",
        )
        manager.complete(
            "observability-delegation",
            result={"recommendations": ["Keep boundaries explicit"]},
        )

        record = manager.execution_record("observability-delegation")
        self.assertEqual(
            [event.status for event in record.timeline],
            [
                ExecutionAuditStatus.CREATED,
                ExecutionAuditStatus.RUNNING,
                ExecutionAuditStatus.RUNNING,
                ExecutionAuditStatus.COMPLETED,
            ],
        )
        self.assertEqual(record.timeline[1].message, "Execution started")
        summary = record.summary()
        self.assertEqual(summary["lifecycle"], ["created", "running", "completed"])
        self.assertTrue(summary["result_available"])
        self.assertEqual(
            manager.execution_summary("observability-delegation")["status"],
            "completed",
        )
        self.assertIn(
            "status=completed",
            manager.operator_summary("observability-delegation"),
        )
        self.assertIn("executor=none", record.operator_summary())

    def test_failure_diagnostics_include_provider_metadata(self):
        manager = DelegationManager()
        manager.accept(self.request("observability-failure"))
        manager.start("observability-failure")
        manager.fail(
            "observability-failure",
            "Hermes stream disconnected",
            metadata={
                "backend": "hermes",
                "failure_state": "partial_stream",
                "run_id": "run-42",
            },
        )

        record = manager.execution_record("observability-failure")
        self.assertEqual(record.terminal_status, "failed")
        self.assertEqual(
            record.failure_diagnostics["failure_state"],
            "partial_stream",
        )
        self.assertEqual(record.failure_diagnostics["run_id"], "run-42")
        self.assertIn("Hermes stream disconnected", record.operator_summary())

    def test_simple_correlation_id_is_carried_into_audit_and_events(self):
        manager = DelegationManager()
        request = DelegationRequest(
            delegation_id="observability-correlation",
            request_id="request-correlation",
            task="Analyze a repository",
            metadata={"correlation_id": "task-correlation-1"},
        )

        manager.execute_with_executor(request)

        record = manager.execution_record("observability-correlation")
        self.assertEqual(record.correlation_id, "task-correlation-1")
        self.assertEqual(
            manager.events("observability-correlation")[1]
            .metadata["execution_trace"]["correlation_id"],
            "task-correlation-1",
        )

    def test_timeline_and_diagnostics_recover_from_persistence(self):
        with TemporaryDirectory() as directory:
            delegation_path = f"{directory}/delegations.json"
            audit_path = f"{directory}/audit.json"
            first = DelegationManager(
                persistence_path=delegation_path,
                audit_path=audit_path,
            )
            first.accept(self.request("observability-recovered"))
            first.start("observability-recovered")
            first.fail(
                "observability-recovered",
                "Network failure",
                metadata={"failure_state": "network_failure"},
            )

            recovered = DelegationManager(
                persistence_path=delegation_path,
                audit_path=audit_path,
            )
            record = recovered.execution_record("observability-recovered")

            self.assertEqual(record.timeline[-1].status, "failed")
            self.assertEqual(
                record.failure_diagnostics["failure_state"],
                "network_failure",
            )
            self.assertEqual(record.summary()["terminal_status"], "failed")


if __name__ == "__main__":
    unittest.main()
