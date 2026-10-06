import unittest

from app.delegation import (
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
    OptInHermesExecutorSelector,
)
from app.delegation.policy import HermesDelegationPolicy
from app.services.hermes_executor import HermesExecutor
from app.services.hermes_http_transport import HermesHttpTransport
from app.services.hermes_transport import TransportHermesClient
from app.services.lightning_executor import InMemoryLightningExecutor
from tests.fake_hermes_service import FakeHermesService, event


class HermesFirstWorkloadTests(unittest.TestCase):
    def test_read_only_repository_analysis_requires_manual_approval(self):
        final_result = {
            "recommendations": [
                "Keep service boundaries explicit.",
                "Document capability ownership.",
            ]
        }
        service = FakeHermesService(
            [[
                event("run.started", message="Analysis started."),
                event("message.delta", delta="Reviewing project structure."),
                event("run.completed", result=final_result),
            ]]
        )
        http_client = service.client()
        executor = HermesExecutor(
            client=TransportHermesClient(
                HermesHttpTransport(http_client, endpoint="https://fake/api")
            )
        )
        selector = OptInHermesExecutorSelector(
            hermes_executor=executor,
            fallback_executor=InMemoryLightningExecutor(),
            policy=HermesDelegationPolicy(enabled=True),
        )
        manager = DelegationManager()
        request = DelegationRequest(
            delegation_id="first-hermes-workload",
            task="Analyze this project structure and provide recommendations.",
            metadata={
                "task_category": "research",
                "dangerous": False,
                "requires_approval": True,
                "approval_id": "first-workload-approval",
                "granted_permissions": ["read_only"],
            },
        )

        try:
            waiting = manager.execute_with_executor(
                request,
                selector=selector,
            )

            self.assertEqual(waiting[-1].status, DelegationStatus.WAITING_APPROVAL)
            self.assertEqual(service.submissions, [])

            manager.approve(
                "first-hermes-workload",
                "first-workload-approval",
            )
            events = manager.execute_with_executor(
                request,
                selector=selector,
            )
        finally:
            http_client.close()

        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertEqual(events[-1].result, final_result)
        self.assertTrue(
            any(event.status == DelegationStatus.PROGRESS for event in events)
        )

        audit = manager.execution_record("first-hermes-workload")
        self.assertEqual(audit.executor_selected, "hermes")
        self.assertEqual(audit.policy_recommendation, "candidate")
        self.assertEqual(audit.approval_state, "approved")
        self.assertEqual(audit.result, final_result)
        self.assertEqual(audit.terminal_status, "completed")


if __name__ == "__main__":
    unittest.main()
