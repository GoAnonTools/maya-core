import unittest

from app.delegation import DelegationRequest, DelegationStatus
from app.delegation.profile_binding import bind_specialist_profile
from app.services.lightning import LightningService
from app.workers.lightning_protocol import LightningWorkerConfig
from app.workers.lightning_transport import (
    LightningRemoteClient,
    LightningTransport,
)
from app.workers.specialists.coding_worker import CodingSpecialistWorker


class ServiceTransport(LightningTransport):
    def __init__(self, service):
        self.service = service

    def connect(self, config):
        self.config = config

    def submit(self, job):
        self.job = job
        return self.service.submit(job)

    def stream_events(self, execution_id):
        yield from self.service.stream_events(execution_id)

    def cancel(self, execution_id):
        self.service.cancel(execution_id)

    def close(self):
        pass


class CodingSpecialistLightningTests(unittest.TestCase):
    def make_request(self):
        return bind_specialist_profile(
            DelegationRequest(
                delegation_id="coding-lightning-1",
                task="Inspect the repository",
                request_id="request-1",
                session_id="session-1",
                required_capabilities=frozenset({"coding"}),
                metadata={"workspace": "test-workspace"},
            ),
            "coding-specialist",
        )

    def make_worker(self, service):
        transport = ServiceTransport(service)
        client = LightningRemoteClient(
            transport,
            LightningWorkerConfig(workspace="test-workspace"),
        )
        return CodingSpecialistWorker(lightning_client=client), transport

    def test_bound_request_becomes_lightning_job_and_events_are_forwarded(self):
        service = LightningService()
        worker, transport = self.make_worker(service)
        request = self.make_request()

        worker.start()
        worker.submit(request)
        events = list(worker.stream_events(request.delegation_id))

        self.assertEqual(transport.job.delegation_id, request.delegation_id)
        self.assertEqual(transport.job.request_id, "request-1")
        self.assertEqual(transport.job.session_id, "session-1")
        self.assertEqual(transport.job.workspace, "test-workspace")
        self.assertEqual(transport.job.capabilities, frozenset({"coding"}))
        self.assertEqual(
            [event.status for event in events],
            [
                DelegationStatus.STARTED,
                DelegationStatus.PROGRESS,
                DelegationStatus.COMPLETED,
            ],
        )
        self.assertEqual(service.health()["active_jobs"], 0)

    def test_cancellation_is_propagated_to_lightning_service(self):
        service = LightningService()
        worker, _ = self.make_worker(service)
        request = self.make_request()

        worker.start()
        worker.submit(request)
        events = worker.stream_events(request.delegation_id)
        self.assertEqual(next(events).status, DelegationStatus.STARTED)
        worker.cancel(request.delegation_id)

        self.assertEqual(
            [event.status for event in events],
            [DelegationStatus.CANCELLED],
        )
        self.assertEqual(service.health()["active_jobs"], 0)


if __name__ == "__main__":
    unittest.main()
