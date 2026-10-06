import asyncio
import unittest

from app.services.lightning_app import LightningJobPayload, create_app


class LightningApplicationTests(unittest.TestCase):
    def setUp(self):
        self.application = create_app()
        self.service = self.application.state.lightning_service

    def test_service_startup(self):
        async def start_and_stop():
            lifecycle = self.application.router.lifespan_context(
                self.application
            )
            await lifecycle.__aenter__()
            self.assertTrue(self.application.state.started)
            await lifecycle.__aexit__(None, None, None)
            self.assertFalse(self.application.state.started)

        asyncio.run(start_and_stop())

    def test_protocol_routes_are_exposed(self):
        routes = {
            (route.path, method)
            for route in self.application.routes
            for method in (route.methods or set())
        }

        self.assertIn(("/health", "GET"), routes)
        self.assertIn(("/jobs", "POST"), routes)
        self.assertIn(("/jobs/{execution_id}/events", "GET"), routes)
        self.assertIn(("/jobs/{execution_id}/cancel", "POST"), routes)

    def test_health(self):
        health = self.service.health()

        self.assertEqual(
            health,
            {
                "service": "lightning",
                "status": "healthy",
                "backend": "in_memory",
                "available": True,
                "active_jobs": 0,
            },
        )

    def test_job_submission(self):
        job = {
            "delegation_id": "delegation-1",
            "request_id": "request-1",
            "session_id": "session-1",
            "workspace": "test-workspace",
            "capabilities": ["coding"],
            "permissions": ["filesystem_read"],
        }
        execution_id = self.service.submit(LightningJobPayload(**job).to_protocol())
        self.assertTrue(
            execution_id.startswith("lightning-execution-")
        )

    def test_event_streaming(self):
        execution_id = self.service.submit(
            _job("delegation-stream")
        )
        events = self.service.stream_events(execution_id)
        events = [
            event.event_type.value
            for event in events
        ]
        self.assertEqual(
            events,
            ["started", "progress", "completed"],
        )

    def test_cancellation(self):
        execution_id = self.service.submit(_job("delegation-cancel"))
        self.service.cancel(execution_id)
        events_response = self.service.stream_events(execution_id)
        event_types = [
            event.event_type.value
            for event in events_response
        ]
        self.assertEqual(event_types, ["started", "cancelled"])


def _job(delegation_id: str):
    from app.workers.lightning_protocol import LightningJob

    return LightningJob(
        delegation_id=delegation_id,
        request_id=None,
        session_id=None,
        workspace="test-workspace",
    )


if __name__ == "__main__":
    unittest.main()
