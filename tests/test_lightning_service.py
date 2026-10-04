import unittest

from app.services.lightning import LightningService
from app.workers.lightning_protocol import (
    LightningEventType,
    LightningJob,
)


class LightningServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = LightningService()
        self.job = LightningJob(
            delegation_id="delegation-1",
            request_id="request-1",
            session_id="session-1",
            workspace="test-workspace",
            capabilities=frozenset({"coding"}),
            permissions=frozenset({"filesystem_read"}),
        )

    def test_job_submission_creates_session(self):
        execution_id = self.service.submit(self.job)
        session = self.service.get_session(execution_id)

        self.assertTrue(execution_id.startswith("lightning-execution-"))
        self.assertEqual(session.session_id, "session-1")
        self.assertEqual(session.job, self.job)
        self.assertEqual(self.service.health()["active_jobs"], 1)

    def test_event_stream_contains_lifecycle_and_progress(self):
        execution_id = self.service.submit(self.job)

        events = list(self.service.stream_events(execution_id))

        self.assertEqual(
            [event.event_type for event in events],
            [
                LightningEventType.STARTED,
                LightningEventType.PROGRESS,
                LightningEventType.COMPLETED,
            ],
        )
        self.assertEqual(events[1].progress, 0.5)
        self.assertEqual(events[-1].session_id, "session-1")
        self.assertEqual(self.service.health()["active_jobs"], 0)

    def test_cancellation_is_emitted(self):
        execution_id = self.service.submit(self.job)
        events = self.service.stream_events(execution_id)

        first = next(events)
        self.assertEqual(first.event_type, LightningEventType.STARTED)
        self.service.cancel(execution_id)
        remaining = list(events)

        self.assertEqual(
            [event.event_type for event in remaining],
            [LightningEventType.CANCELLED],
        )
        self.assertEqual(self.service.health()["active_jobs"], 0)

    def test_health_check(self):
        health = self.service.health()

        self.assertEqual(health["service"], "lightning")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["backend"], "in_memory")
        self.assertEqual(health["active_jobs"], 0)
