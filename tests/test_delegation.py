import unittest

from app.delegation import (
    DelegationEvent,
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
)
from app.workers import WorkerCapability, WorkerRegistry, WorkerRole
from app.workers.specialist import SpecialistWorker


class FakeSpecialistWorker(SpecialistWorker):
    def __init__(self):
        self.submitted = []
        self.cancelled = []
        self.manager = None
        self.active_delegation_id = None

    def capability(self):
        return WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Test specialist",
            capabilities=frozenset({"coding"}),
        )

    def submit(self, request):
        self.submitted.append(request.delegation_id)
        self.active_delegation_id = request.delegation_id
        return f"execution-{request.delegation_id}"

    def stream_events(self, delegation_id):
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.PROGRESS,
            progress=0.5,
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


class DelegationManagerTests(unittest.TestCase):
    def setUp(self):
        self.emitted = []
        self.manager = DelegationManager(self.emitted.append)
        self.request = DelegationRequest(
            delegation_id="delegation-1",
            task="Prepare a report",
            metadata={"source": "test"},
        )

    def test_lifecycle_emits_structured_events(self):
        accepted = self.manager.accept(self.request)
        started = self.manager.start("delegation-1")
        progress = self.manager.progress(
            "delegation-1",
            0.5,
            message="Half complete",
        )
        completed = self.manager.complete(
            "delegation-1",
            result={"ok": True},
        )

        self.assertIsInstance(accepted, DelegationEvent)
        self.assertEqual(
            [event.status for event in self.emitted],
            [
                DelegationStatus.PENDING,
                DelegationStatus.STARTED,
                DelegationStatus.PROGRESS,
                DelegationStatus.COMPLETED,
            ],
        )
        self.assertEqual(progress.progress, 0.5)
        self.assertEqual(completed.result, {"ok": True})
        self.assertEqual(
            self.manager.get_status("delegation-1"),
            DelegationStatus.COMPLETED,
        )

    def test_failure_lifecycle(self):
        self.manager.accept(self.request)
        self.manager.start("delegation-1")

        event = self.manager.fail("delegation-1", "Delegated task failed")

        self.assertEqual(event.status, DelegationStatus.FAILED)
        self.assertEqual(event.error, "Delegated task failed")
        self.assertEqual(
            self.manager.get_status("delegation-1"),
            DelegationStatus.FAILED,
        )

    def test_cancellation_from_pending_and_active_states(self):
        self.manager.accept(self.request)
        event = self.manager.cancel("delegation-1", "No longer needed")

        self.assertEqual(event.status, DelegationStatus.CANCELLED)
        self.assertEqual(event.message, "No longer needed")

    def test_invalid_transitions_are_rejected(self):
        self.manager.accept(self.request)

        with self.assertRaises(ValueError):
            self.manager.progress("delegation-1", 0.5)

        self.manager.start("delegation-1")
        self.manager.complete("delegation-1")

        with self.assertRaises(ValueError):
            self.manager.cancel("delegation-1")

    def test_request_validation_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            self.manager.accept(DelegationRequest("", "task"))

        with self.assertRaises(ValueError):
            self.manager.accept(DelegationRequest("id", "   "))

        self.manager.accept(self.request)
        with self.assertRaises(ValueError):
            self.manager.accept(self.request)

    def test_progress_range_is_validated(self):
        self.manager.accept(self.request)
        self.manager.start("delegation-1")

        with self.assertRaises(ValueError):
            self.manager.progress("delegation-1", 1.1)

        with self.assertRaises(ValueError):
            self.manager.progress("delegation-1", -0.1)

    def test_event_history_is_returned_as_a_copy(self):
        self.manager.accept(self.request)
        events = self.manager.events("delegation-1")
        events.clear()

        self.assertEqual(len(self.manager.events("delegation-1")), 1)

    def test_executable_specialist_receives_delegation_and_events_forward(self):
        worker = FakeSpecialistWorker()
        registry = WorkerRegistry()
        registry.register_specialist("specialist", worker)
        manager = DelegationManager(
            self.emitted.append,
            worker_registry=registry,
        )
        request = DelegationRequest(
            "delegation-specialist",
            "Review code",
            selected_worker={"worker_id": "specialist"},
            required_capabilities=frozenset({"coding"}),
        )

        events = manager.execute(request)

        self.assertEqual(worker.submitted, ["delegation-specialist"])
        self.assertEqual(
            [event.status for event in events],
            [
                DelegationStatus.PENDING,
                DelegationStatus.STARTED,
                DelegationStatus.PROGRESS,
                DelegationStatus.COMPLETED,
            ],
        )
        self.assertEqual(
            [event.status for event in self.emitted],
            [event.status for event in events],
        )
        self.assertEqual(manager.get_status("delegation-specialist"), DelegationStatus.COMPLETED)

    def test_missing_executable_specialist_fails_cleanly(self):
        registry = WorkerRegistry()
        registry.register_capability(
            WorkerCapability(
                worker_id="specialist",
                role=WorkerRole.SPECIALIST,
                display_name="Unavailable specialist",
                capabilities=frozenset({"coding"}),
                availability=True,
            )
        )
        manager = DelegationManager(worker_registry=registry)
        request = DelegationRequest(
            "delegation-missing",
            "Review code",
            selected_worker={"worker_id": "specialist"},
        )

        events = manager.execute(request)

        self.assertEqual(events[-1].status, DelegationStatus.FAILED)
        self.assertIn("executable specialist", events[-1].error)

    def test_cancellation_propagates_to_active_specialist(self):
        worker = FakeSpecialistWorker()
        manager = None

        class CancellingWorker(FakeSpecialistWorker):
            def stream_events(self, delegation_id):
                manager.cancel("delegation-cancel")
                yield DelegationEvent(
                    delegation_id=delegation_id,
                    status=DelegationStatus.CANCELLED,
                )

        worker = CancellingWorker()
        registry = WorkerRegistry()
        registry.register_specialist("specialist", worker)
        manager = DelegationManager(worker_registry=registry)
        request = DelegationRequest(
            "delegation-cancel",
            "Review code",
            selected_worker={"worker_id": "specialist"},
        )

        events = manager.execute(request)

        self.assertEqual(worker.cancelled, ["execution-delegation-cancel"])
        self.assertEqual(events[-1].status, DelegationStatus.CANCELLED)
