import unittest

from app.delegation import (
    DelegationEvent,
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
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
