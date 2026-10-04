import unittest

from app.delegation import DelegationEvent, DelegationRequest, DelegationStatus
from app.workers import SpecialistWorker, WorkerCapability, WorkerRole


class FakeSpecialistWorker(SpecialistWorker):
    def __init__(self):
        self.requests = {}
        self.cancelled = []

    def submit(self, request):
        self.requests[request.delegation_id] = request
        return request.delegation_id

    def capability(self):
        return WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Test specialist",
            capabilities=frozenset({"coding"}),
        )

    def stream_events(self, delegation_id):
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.STARTED,
        )
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            result={"ok": True},
        )

    def cancel(self, delegation_id):
        self.cancelled.append(delegation_id)

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


class SpecialistWorkerContractTests(unittest.TestCase):
    def test_contract_is_abstract(self):
        self.assertTrue(getattr(SpecialistWorker, "__abstractmethods__"))

        with self.assertRaises(TypeError):
            SpecialistWorker()

    def test_supports_submission_and_event_streaming(self):
        worker = FakeSpecialistWorker()
        request = DelegationRequest("task-1", "Inspect a project")

        self.assertEqual(worker.submit(request), "task-1")
        events = list(worker.stream_events("task-1"))

        self.assertEqual(
            [event.status for event in events],
            [DelegationStatus.STARTED, DelegationStatus.COMPLETED],
        )

    def test_supports_cancellation_and_terminal_reporting(self):
        worker = FakeSpecialistWorker()

        worker.cancel("task-1")
        completed = worker.complete("task-1", {"answer": 42})
        failed = worker.fail("task-2", "Task failed")

        self.assertEqual(worker.cancelled, ["task-1"])
        self.assertEqual(completed.status, DelegationStatus.COMPLETED)
        self.assertEqual(completed.result, {"answer": 42})
        self.assertEqual(failed.status, DelegationStatus.FAILED)
        self.assertEqual(failed.error, "Task failed")
