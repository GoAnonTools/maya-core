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


class MayaHermesUserWorkflowTests(unittest.TestCase):
    """Exercise the dashboard's first read-only Hermes workload contract."""

    def test_dashboard_trigger_to_hermes_result(self):
        task = "Analyze this project structure and provide recommendations."
        result = {"recommendations": ["Keep service boundaries explicit."]}
        service = FakeHermesService(
            [[
                event("run.started", message="Analysis started."),
                event("message.delta", delta="Reviewing project structure."),
                event("run.completed", result=result),
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
            delegation_id="dashboard-first-hermes",
            task=task,
            metadata={
                "task_category": "research",
                "dangerous": False,
                "requires_approval": True,
                "approval_id": "dashboard-first-hermes-approval",
                "granted_permissions": ["read_only"],
            },
        )

        try:
            # This is the action represented by the dashboard developer trigger.
            waiting = manager.execute_with_executor(request, selector=selector)
            self.assertEqual(waiting[-1].status, DelegationStatus.WAITING_APPROVAL)
            self.assertEqual(service.submissions, [])

            # Maya owns the approval decision; Hermes never self-approves.
            manager.approve(
                request.delegation_id,
                "dashboard-first-hermes-approval",
            )
            events = manager.execute_with_executor(request, selector=selector)

            self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
            self.assertEqual(events[-1].result, result)
            self.assertEqual(service.submissions[0]["task"], task)

            record = manager.execution_record(request.delegation_id)
            self.assertEqual(record.executor_selected, "hermes")
            self.assertEqual(record.approval_state, "approved")
            self.assertEqual(record.terminal_status, "completed")

            self.assertTrue(manager.events(request.delegation_id))
        finally:
            http_client.close()


if __name__ == "__main__":
    unittest.main()
