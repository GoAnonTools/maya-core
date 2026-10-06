import unittest
from tempfile import TemporaryDirectory

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
from app.workers.lightning_protocol import LightningEventType, LightningJob
from tests.fake_hermes_service import FakeHermesService, event


class HermesEndToEndTests(unittest.TestCase):
    def test_complete_opt_in_delegation_flow(self):
        service = FakeHermesService(
            [
                [
                    event("run.started", message="started"),
                    event("message.delta", delta="Working"),
                    event("tool.started", tool_name="search"),
                    event("tool.completed", tool_name="search"),
                    event("run.completed", result={"answer": "done"}),
                ],
            ]
        )
        http_client = service.client()
        transport = HermesHttpTransport(http_client, endpoint="https://fake/api")
        executor = HermesExecutor(
            client=TransportHermesClient(transport),
        )
        selector = OptInHermesExecutorSelector(
            hermes_executor=executor,
            fallback_executor=InMemoryLightningExecutor(),
            policy=HermesDelegationPolicy(enabled=True),
        )
        manager = DelegationManager()
        request = DelegationRequest(
            delegation_id="e2e-complete",
            task="Implement a coding change",
            metadata={
                "task_category": "coding",
                "requires_approval": True,
                "approval_id": "approval-e2e",
            },
        )

        try:
            waiting = manager.execute_with_executor(
                request,
                selector=selector,
            )
            self.assertEqual(waiting[-1].status, DelegationStatus.WAITING_APPROVAL)
            self.assertEqual(service.submissions, [])

            manager.approve("e2e-complete", "approval-e2e")
            events = manager.execute_with_executor(
                request,
                selector=selector,
            )

            self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
            self.assertEqual(
                [event.status for event in events[-5:]],
                [
                    DelegationStatus.STARTED,
                    DelegationStatus.PROGRESS,
                    DelegationStatus.PROGRESS,
                    DelegationStatus.PROGRESS,
                    DelegationStatus.COMPLETED,
                ],
            )
            self.assertEqual(service.submissions[0]["task"], request.task)
            record = manager.execution_record("e2e-complete")
            self.assertEqual(record.executor_selected, "hermes")
            self.assertEqual(record.policy_recommendation, "candidate")
            self.assertEqual(record.approval_state, "approved")
            self.assertEqual(record.terminal_status, "completed")
            self.assertEqual(record.history[-1], "completed")

            execution_id = next(iter(executor._mappings))
            mapping = executor.run_mapping(execution_id)
            self.assertEqual(mapping.run_id, "fake-run-1")
            self.assertEqual(mapping.delegation_id, "e2e-complete")
        finally:
            http_client.close()

    def test_failure_event_propagates_to_delegation_and_audit(self):
        service = FakeHermesService(
            [[
                event("run.started"),
                event("run.failed", error="specialist failed"),
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
            policy=HermesDelegationPolicy(enabled=True),
        )
        manager = DelegationManager()

        try:
            events = manager.execute_with_executor(
                DelegationRequest(
                    delegation_id="e2e-failure",
                    task="Implement a coding change",
                    metadata={"task_category": "coding"},
                ),
                selector=selector,
            )

            self.assertEqual(events[-1].status, DelegationStatus.FAILED)
            self.assertEqual(events[-1].error, "specialist failed")
            record = manager.execution_record("e2e-failure")
            self.assertEqual(record.terminal_status, "failed")
            self.assertEqual(record.error_metadata["error"], "specialist failed")
        finally:
            http_client.close()

    def test_cancellation_and_run_mapping_recover_after_restart(self):
        service = FakeHermesService()
        http_client = service.client()
        with TemporaryDirectory() as directory:
            mapping_path = f"{directory}/hermes-runs.json"
            transport = HermesHttpTransport(
                http_client,
                endpoint="https://fake/api",
            )
            client = TransportHermesClient(transport)
            first = HermesExecutor(
                client=client,
                persistence_path=mapping_path,
            )
            job = LightningJob(
                delegation_id="e2e-cancel",
                request_id="request-cancel",
                session_id="session-cancel",
                workspace="workspace",
            )

            execution_id = first.submit(job)
            mapping = first.run_mapping(execution_id)
            first.cancel(execution_id)

            self.assertEqual(service.cancelled_runs, [mapping.run_id])
            self.assertEqual(
                list(first.stream_events(execution_id))[0].event_type,
                LightningEventType.CANCELLED,
            )

            recovered = HermesExecutor(
                client=client,
                persistence_path=mapping_path,
            )
            recovered_mapping = recovered.run_mapping(execution_id)
            self.assertEqual(recovered_mapping.run_id, mapping.run_id)
            self.assertTrue(recovered.get_session(execution_id).cancelled)

        http_client.close()


if __name__ == "__main__":
    unittest.main()
