import unittest

from app.delegation import (
    DelegationEvent,
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
)
from app.orchestration import NormalizedRequest, Orchestrator
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole
from app.workers.specialist import SpecialistWorker


class TestSpecialistWorker(SpecialistWorker):
    """Minimal executable specialist used only by these tests."""

    def __init__(self):
        self.submissions = []
        self.cancelled = set()

    def capability(self):
        return WorkerCapability(
            worker_id="test-specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Test specialist",
            capabilities=frozenset({"coding"}),
            metadata={"execution": "test-only"},
        )

    def submit(self, request: DelegationRequest) -> str:
        execution_id = f"test-execution-{request.delegation_id}"
        self.submissions.append((execution_id, request))
        return execution_id

    def stream_events(self, delegation_id: str):
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.STARTED,
            metadata={"source": "test-specialist"},
        )

        if delegation_id in self.cancelled:
            yield DelegationEvent(
                delegation_id=delegation_id,
                status=DelegationStatus.CANCELLED,
            )
            return

        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.PROGRESS,
            progress=0.5,
        )
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            progress=1.0,
            result={"worker": "test-specialist", "ok": True},
        )

    def cancel(self, delegation_id: str) -> None:
        self.cancelled.add(delegation_id)

    def complete(self, delegation_id: str, result=None) -> DelegationEvent:
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            result=result,
        )

    def fail(self, delegation_id: str, error: str) -> DelegationEvent:
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.FAILED,
            error=error,
        )


class DefaultWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok", "message": "default"}

    def stream(self, context, route):
        yield "default"


class SpecialistAdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.specialist = TestSpecialistWorker()
        self.registry = WorkerRegistry()
        self.registry.register(
            "default",
            DefaultWorker(),
            WorkerCapability(
                worker_id="default",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Default",
                capabilities=frozenset({"conversational", "chat"}),
            ),
        )
        self.registry.register_specialist(
            "test-specialist",
            self.specialist,
        )

    def test_routing_to_delegation_to_specialist_events(self):
        orchestrator = Orchestrator(
            self.registry,
            default_worker_id="default",
        )
        delegation = orchestrator.prepare_delegation_request(
            NormalizedRequest(
                context={"message": "Review this code"},
                route={},
                metadata={"required_capabilities": ["coding"]},
                request_id="request-1",
                session_id="session-1",
            )
        )
        manager = DelegationManager(worker_registry=self.registry)

        events = manager.execute(delegation)

        self.assertEqual(
            delegation.selected_worker["worker_id"],
            "test-specialist",
        )
        self.assertEqual(
            delegation.required_capabilities,
            frozenset({"coding"}),
        )
        self.assertEqual(len(self.specialist.submissions), 1)
        self.assertEqual(
            [event.status for event in events],
            [
                DelegationStatus.PENDING,
                DelegationStatus.STARTED,
                DelegationStatus.STARTED,
                DelegationStatus.PROGRESS,
                DelegationStatus.COMPLETED,
            ],
        )
        self.assertEqual(events[-1].result["ok"], True)

    def test_test_worker_supports_cancellation(self):
        request = DelegationRequest("cancel-1", "Cancel me")
        execution_id = self.specialist.submit(request)
        self.specialist.cancel(execution_id)

        statuses = [
            event.status
            for event in self.specialist.stream_events(execution_id)
        ]

        self.assertEqual(
            statuses,
            [DelegationStatus.STARTED, DelegationStatus.CANCELLED],
        )
