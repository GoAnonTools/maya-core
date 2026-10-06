import json
import unittest

import httpx

from app.services.hermes_executor import HermesExecutor
from app.services.hermes_http_transport import (
    HermesHttpTransport,
    HermesHttpTransportConfig,
)
from app.services.hermes_protocol import HermesJob
from app.services.hermes_transport import TransportHermesClient
from app.workers.lightning_protocol import LightningEventType, LightningJob


class HermesHttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            self.assertEqual(
                request.headers["authorization"],
                "Bearer test-token",
            )

            if request.method == "POST" and request.url.path == "/api/runs":
                payload = json.loads(request.content)
                self.assertEqual(payload["delegation_id"], "delegation-1")
                return httpx.Response(
                    201,
                    json={"run_id": "run-1"},
                    request=request,
                )

            if request.method == "GET" and request.url.path == "/api/runs/run-1/events":
                sse = (
                    "event: run.started\n"
                    "data: {\"run_id\": \"run-1\"}\n\n"
                    "event: message.delta\n"
                    "data: {\"delta\": \"Hello\"}\n\n"
                    "event: approval.request\n"
                    "data: {\"approval_id\": \"approval-1\"}\n\n"
                    "event: run.completed\n"
                    "data: {\"result\": {\"answer\": \"done\"}}\n\n"
                    "data: [DONE]\n\n"
                )
                return httpx.Response(
                    200,
                    headers={"content-type": "text/event-stream"},
                    content=sse.encode(),
                    request=request,
                )

            if request.method == "POST" and request.url.path == "/api/runs/run-1/cancel":
                return httpx.Response(204, request=request)

            if request.method == "GET" and request.url.path == "/api/health":
                return httpx.Response(
                    200,
                    json={"status": "ok"},
                    request=request,
                )

            return httpx.Response(404, request=request)

        self.http_client = httpx.Client(transport=httpx.MockTransport(handler))
        self.transport = HermesHttpTransport(
            self.http_client,
            endpoint="https://hermes.test/api",
            auth_token="test-token",
        )

    def tearDown(self):
        self.http_client.close()

    def test_submit_stream_cancel_and_health(self):
        job = HermesJob(delegation_id="delegation-1", task="Say hello")

        run_id = self.transport.submit(job)
        events = list(self.transport.stream_events(run_id))
        self.transport.cancel(run_id)
        health = self.transport.health()

        self.assertEqual(run_id, "run-1")
        self.assertEqual(
            [event.event_type.value for event in events],
            [
                "run.started",
                "message.delta",
                "approval.request",
                "run.completed",
            ],
        )
        self.assertEqual(events[1].delta, "Hello")
        self.assertEqual(events[2].approval_id, "approval-1")
        self.assertEqual(events[3].result, {"answer": "done"})
        self.assertTrue(health["available"])
        self.assertEqual(
            [request.url.path for request in self.requests],
            [
                "/api/runs",
                "/api/runs/run-1/events",
                "/api/runs/run-1/cancel",
                "/api/health",
            ],
        )

    def test_executor_uses_http_transport_without_approving(self):
        client = TransportHermesClient(self.transport)
        executor = HermesExecutor(client=client)
        job = LightningJob(
            delegation_id="delegation-1",
            request_id="request-1",
            session_id="session-1",
            workspace="workspace",
        )

        execution_id = executor.submit(job)
        events = list(executor.stream_events(execution_id))

        self.assertEqual(
            [event.event_type for event in events],
            [
                LightningEventType.STARTED,
                LightningEventType.PROGRESS,
                LightningEventType.PROGRESS,
                LightningEventType.COMPLETED,
            ],
        )
        self.assertTrue(events[2].metadata["approval_required"])
        self.assertEqual(events[2].metadata["approval_id"], "approval-1")
        self.assertFalse(any(request.url.path.endswith("/approve") for request in self.requests))

    def test_stream_reconnects_with_last_event_id_and_deduplicates(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                content = (
                    "id: event-1\n"
                    "event: run.started\n"
                    "data: {}\n\n"
                    "id: event-2\n"
                    "event: message.delta\n"
                    "data: {\"delta\": \"partial\"}\n\n"
                )
            else:
                self.assertEqual(request.headers["last-event-id"], "event-2")
                content = (
                    "id: event-2\n"
                    "event: message.delta\n"
                    "data: {\"delta\": \"partial\"}\n\n"
                    "id: event-3\n"
                    "event: run.completed\n"
                    "data: {\"result\": \"done\"}\n\n"
                )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=content.encode(),
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        transport = HermesHttpTransport(
            client,
            config=HermesHttpTransportConfig(
                endpoint="https://hermes.test",
                max_reconnects=1,
            ),
        )
        try:
            events = list(transport.stream_events("run-1"))
        finally:
            client.close()

        self.assertEqual(len(calls), 2)
        self.assertEqual(
            [event.event_id for event in events],
            ["event-1", "event-2", "event-3"],
        )


if __name__ == "__main__":
    unittest.main()
