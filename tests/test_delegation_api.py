import asyncio
import unittest

from fastapi import HTTPException
from starlette.responses import StreamingResponse

from app.delegation import DelegationManager, DelegationRequest
from app.delegation.api import create_delegation_observability_app


class DelegationObservabilityApiTests(unittest.TestCase):
    def setUp(self):
        self.manager = DelegationManager()
        self.manager.accept(
            DelegationRequest(
                delegation_id="api-delegation",
                task="Analyze a repository",
            )
        )
        self.manager.start("api-delegation", message="Started")
        self.manager.progress(
            "api-delegation",
            0.5,
            message="Halfway",
        )
        self.manager.complete(
            "api-delegation",
            result={"recommendations": ["Keep modules focused"]},
        )
        self.application = create_delegation_observability_app(self.manager)

    def endpoint(self, path, method="GET"):
        return next(
            route.endpoint
            for route in self.application.routes
            if route.path == path and method in (route.methods or set())
        )

    def test_read_only_routes_are_exposed(self):
        routes = {
            (route.path, method)
            for route in self.application.routes
            for method in (route.methods or set())
        }

        self.assertIn(("/delegations/{delegation_id}/status", "GET"), routes)
        self.assertIn(("/delegations/{delegation_id}/timeline", "GET"), routes)
        self.assertIn(("/delegations/{delegation_id}/audit", "GET"), routes)
        self.assertIn(("/delegations/{delegation_id}/events", "GET"), routes)
        self.assertNotIn(("/delegations/{delegation_id}/approve", "POST"), routes)

    def test_status_endpoint(self):
        response = self.endpoint("/delegations/{delegation_id}/status")(
            "api-delegation"
        )

        self.assertEqual(response["delegation_id"], "api-delegation")
        self.assertEqual(response["status"], "completed")
        self.assertIsNone(response["pending_approval"])

    def test_timeline_endpoint(self):
        response = self.endpoint("/delegations/{delegation_id}/timeline")(
            "api-delegation"
        )

        self.assertEqual(response["delegation_id"], "api-delegation")
        self.assertEqual(response["timeline"][-1]["status"], "completed")
        self.assertEqual(response["timeline"][1]["message"], "Started")

    def test_audit_summary_endpoint(self):
        response = self.endpoint("/delegations/{delegation_id}/audit")(
            "api-delegation"
        )

        self.assertEqual(response["summary"]["status"], "completed")
        self.assertTrue(response["summary"]["result_available"])
        self.assertIn("status=completed", response["operator_summary"])

    def test_sse_event_stream_replays_delegation_events(self):
        response = self.endpoint("/delegations/{delegation_id}/events")(
            "api-delegation"
        )

        self.assertIsInstance(response, StreamingResponse)

        async def read():
            return [chunk async for chunk in response.body_iterator]

        body = "".join(asyncio.run(read()))
        self.assertIn("event: lifecycle", body)
        self.assertIn('"status": "completed"', body)
        self.assertIn("Keep modules focused", body)

    def test_unknown_delegation_returns_not_found(self):
        with self.assertRaises(HTTPException) as context:
            self.endpoint("/delegations/{delegation_id}/status")(
                "missing-delegation"
            )

        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
