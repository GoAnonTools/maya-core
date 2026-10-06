"""In-memory Hermes HTTP/SSE service used by end-to-end tests."""

from collections.abc import Iterable
import json
from typing import Any

import httpx

from app.services.hermes_protocol import HermesEvent


class FakeHermesService:
    """A deterministic Hermes-like service with no network dependency."""

    def __init__(self, scripts: Iterable[list[dict[str, Any]]] = ()) -> None:
        self._scripts = list(scripts)
        self._runs: dict[str, list[dict[str, Any]]] = {}
        self._next_run = 1
        self.submissions: list[dict[str, Any]] = []
        self.cancelled_runs: list[str] = []

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/runs":
            payload = json.loads(request.content)
            run_id = f"fake-run-{self._next_run}"
            self._next_run += 1
            script = self._scripts.pop(0) if self._scripts else []
            self._runs[run_id] = script
            self.submissions.append(payload)
            return httpx.Response(
                201,
                json={"run_id": run_id},
                request=request,
            )

        if request.method == "GET" and request.url.path.endswith("/events"):
            run_id = request.url.path.split("/")[-2]
            events = self._runs.get(run_id, [])
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=self._sse(events),
                request=request,
            )

        if request.method == "POST" and request.url.path.endswith("/cancel"):
            run_id = request.url.path.split("/")[-2]
            self.cancelled_runs.append(run_id)
            return httpx.Response(204, request=request)

        if request.method == "GET" and request.url.path == "/api/health":
            return httpx.Response(
                200,
                json={"status": "ok", "available": True},
                request=request,
            )

        return httpx.Response(404, request=request)

    @staticmethod
    def _sse(events: list[dict[str, Any]]) -> bytes:
        chunks: list[str] = []
        for index, event in enumerate(events, start=1):
            event_name = event["event"]
            payload = dict(event.get("data", {}))
            chunks.append(f"id: event-{index}\n")
            chunks.append(f"event: {event_name}\n")
            chunks.append(f"data: {json.dumps(payload)}\n\n")
        chunks.append("data: [DONE]\n\n")
        return "".join(chunks).encode()


def event(event_name: str, **data: Any) -> dict[str, Any]:
    """Build one fake Hermes SSE event definition."""
    return {"event": event_name, "data": data}


def event_from_model(value: HermesEvent) -> dict[str, Any]:
    """Convert a normalized Hermes event into a fake SSE definition."""
    data = {
        key: item
        for key, item in {
            "run_id": value.run_id,
            "message": value.message,
            "progress": value.progress,
            "result": value.result,
            "error": value.error,
            "approval_id": value.approval_id,
            "delta": value.delta,
            "tool_name": value.tool_name,
            "tool_call_id": value.tool_call_id,
            "metadata": value.metadata,
        }.items()
        if item is not None
    }
    return event(value.event_type.value, **data)
