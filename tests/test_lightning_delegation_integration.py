import unittest

from app.delegation import (
    DelegationEvent,
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
)
from app.orchestration import NormalizedRequest, Orchestrator
from app.services.lightning import LightningService
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
    LightningWorkerConfig,
)
from app.workers.lightning_transport import (
    LightningRemoteClient,
    LightningTransport,
)
from app.workers.specialist import SpecialistWorker


class ServiceTransport(LightningTransport):
    """In-memory transport that forwards to the Lightning service skeleton."""

    def __init__(self, service):
        self.service = service
        self.connected = False

    def connect(self, config):
        self.connected = True

    def submit(self, job):
        return self.service.submit(job)

    def stream_events(self, execution_id):
        yield from self.service.stream_events(execution_id)

    def cancel(self, execution_id):
        self.service.cancel(execution_id)

    def close(self):
        self.connected = False


class ServiceBackedTestLightningWorker(SpecialistWorker):
    """Test-only SpecialistWorker wired to the fake transport boundary."""

    def __init__(self, service, cancel_after_started=False):
        self.client = LightningRemoteClient(
            ServiceTransport(service),
            LightningWorkerConfig(workspace="test-workspace"),
        )
        self.cancel_after_started = cancel_after_started

    def capability(self):
        return WorkerCapability(
            worker_id="test-lightning",
            role=WorkerRole.SPECIALIST,
            display_name="Test Lightning specialist",
            capabilities=frozenset({"coding"}),
            availability=True,
            metadata={"execution": "test-only"},
        )

    def start(self):
        self.client.start()

    def submit(self, request: DelegationRequest):
        job = LightningJob(
            delegation_id=request.delegation_id,
            request_id=request.request_id,
            session_id=request.session_id,
            workspace="test-workspace",
            capabilities=request.required_capabilities,
        )
        return self.client.submit(job)

    def stream_events(self, execution_id):
        for event in self.client.stream_events(execution_id):
            delegation_event = self._to_delegation_event(event)

            if (
                self.cancel_after_started
                and event.event_type == LightningEventType.STARTED
            ):
                self.cancel(execution_id)

            yield delegation_event

    def cancel(self, execution_id):
        self.client.cancel(execution_id)

    def complete(self, delegation_id, result=None):
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            result=result,
        )

    def fail(self, delegation_id, error):
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.FAILED,
            error=error,
        )

    @staticmethod
    def _to_delegation_event(event: LightningEvent):
        status_by_type = {
            LightningEventType.STARTED: DelegationStatus.STARTED,
            LightningEventType.PROGRESS: DelegationStatus.PROGRESS,
            LightningEventType.COMPLETED: DelegationStatus.COMPLETED,
            LightningEventType.FAILED: DelegationStatus.FAILED,
            LightningEventType.CANCELLED: DelegationStatus.CANCELLED,
        }
        return DelegationEvent(
            delegation_id=event.delegation_id,
            status=status_by_type[event.event_type],
            progress=event.progress,
            message=event.message,
            result=event.result,
            error=event.error,
            metadata=event.metadata,
        )


class FailingLightningService(LightningService):
    def stream_events(self, execution_id):
        session = self.get_session(execution_id)
        yield self._event(session, LightningEventType.STARTED)
        session.terminal = True
        yield self._event(
            session,
            LightningEventType.FAILED,
            message="In-memory failure.",
        )


class DefaultWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok", "message": "default"}

    def stream(self, context, route):
        yield "default"


class LightningDelegationIntegrationTests(unittest.TestCase):
    def build_orchestrator(self, specialist):
        registry = WorkerRegistry()
        registry.register(
            "default",
            DefaultWorker(),
            WorkerCapability(
                worker_id="default",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Default",
                capabilities=frozenset({"conversational", "chat"}),
            ),
        )
        registry.register_specialist("test-lightning", specialist)
        return Orchestrator(registry, default_worker_id="default"), registry

    def make_delegation(self, orchestrator):
        return orchestrator.prepare_delegation_request(
            NormalizedRequest(
                context={"message": "Review this code"},
                route={},
                metadata={"required_capabilities": ["coding"]},
                request_id="request-1",
                session_id="session-1",
            )
        )

    def test_job_creation_event_propagation_and_completion(self):
        service = LightningService()
        worker = ServiceBackedTestLightningWorker(service)
        worker.start()
        orchestrator, registry = self.build_orchestrator(worker)
        delegation = self.make_delegation(orchestrator)

        events = DelegationManager(worker_registry=registry).execute(delegation)

        self.assertEqual(delegation.required_capabilities, frozenset({"coding"}))
        self.assertEqual(service.health()["active_jobs"], 0)
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
        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)

    def test_cancellation_propagates_through_transport_to_service(self):
        service = LightningService()
        worker = ServiceBackedTestLightningWorker(
            service,
            cancel_after_started=True,
        )
        worker.start()
        orchestrator, registry = self.build_orchestrator(worker)
        delegation = self.make_delegation(orchestrator)

        events = DelegationManager(worker_registry=registry).execute(delegation)

        self.assertEqual(events[-1].status, DelegationStatus.CANCELLED)

    def test_service_failure_propagates_as_delegation_failure(self):
        service = FailingLightningService()
        worker = ServiceBackedTestLightningWorker(service)
        worker.start()
        orchestrator, registry = self.build_orchestrator(worker)
        delegation = self.make_delegation(orchestrator)

        events = DelegationManager(worker_registry=registry).execute(delegation)

        self.assertEqual(events[-1].status, DelegationStatus.FAILED)
        self.assertEqual(events[-1].message, "In-memory failure.")
