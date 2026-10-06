"""HTTP/SSE implementation of the Hermes transport boundary."""

from dataclasses import asdict, dataclass
import json
import logging
import os
from collections.abc import Iterable, Iterator
from typing import Any

import httpx

from app.services.hermes_protocol import (
    HermesEvent,
    HermesEventType,
    HermesJob,
)
from app.services.hermes_transport import HermesTransport
from app.services.hermes_errors import (
    HermesNetworkError,
    HermesPartialStreamError,
    HermesTimeoutError,
    HermesUnknownTerminalState,
)


@dataclass(frozen=True)
class HermesHttpTransportConfig:
    """Configurable Hermes HTTP endpoint and authentication placeholder."""

    endpoint: str
    auth_token: str | None = None
    submit_path: str = "/runs"
    events_path: str = "/runs/{run_id}/events"
    cancel_path: str = "/runs/{run_id}/cancel"
    health_path: str = "/health"
    submission_timeout: float = 10.0
    stream_timeout: float = 30.0
    cancellation_timeout: float = 10.0
    max_reconnects: int = 2

    @classmethod
    def from_environment(cls) -> "HermesHttpTransportConfig":
        return cls(
            endpoint=os.getenv("MAYA_HERMES_ENDPOINT", ""),
            auth_token=os.getenv("MAYA_HERMES_AUTH_TOKEN"),
            submission_timeout=float(
                os.getenv("MAYA_HERMES_SUBMISSION_TIMEOUT", "10")
            ),
            stream_timeout=float(
                os.getenv("MAYA_HERMES_STREAM_TIMEOUT", "30")
            ),
            cancellation_timeout=float(
                os.getenv("MAYA_HERMES_CANCELLATION_TIMEOUT", "10")
            ),
            max_reconnects=int(os.getenv("MAYA_HERMES_MAX_RECONNECTS", "2")),
        )


class HermesHttpTransport(HermesTransport):
    """Call a Hermes Agent API through an injected HTTP client.

    The HTTP client is required to keep network creation and ownership outside
    this boundary. Tests can provide ``httpx.MockTransport`` or a fake client.
    """

    def __init__(
        self,
        client: Any,
        endpoint: str | None = None,
        auth_token: str | None = None,
        *,
        config: HermesHttpTransportConfig | None = None,
    ) -> None:
        if config is not None and endpoint is not None:
            raise ValueError("Provide config or endpoint, not both")

        self._client = client
        self._logger = logging.getLogger(__name__)
        self._config = config or HermesHttpTransportConfig(
            endpoint=endpoint or "",
            auth_token=auth_token,
        )
        if not self._config.endpoint.strip():
            raise ValueError("Hermes endpoint must not be empty")

    def submit(self, job: HermesJob) -> str:
        payload = asdict(job)
        payload["capabilities"] = sorted(job.capabilities)
        payload["permissions"] = sorted(job.permissions)

        try:
            response = self._client.post(
                self._url(self._config.submit_path),
                json=payload,
                headers=self._headers(),
                timeout=self._config.submission_timeout,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise HermesTimeoutError(f"Hermes submit timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise HermesNetworkError(f"Hermes submit failed: {exc}") from exc
        except ValueError as exc:
            raise HermesNetworkError(
                f"Hermes submit response was invalid: {exc}"
            ) from exc

        run_id = body.get("run_id") or body.get("id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise RuntimeError("Hermes submit response did not include run_id")
        return run_id

    def stream_events(self, run_id: str) -> Iterator[HermesEvent]:
        path = self._config.events_path.format(run_id=run_id)
        last_event_id: str | None = None
        seen_event_ids: set[str] = set()
        saw_event = False

        for attempt in range(self._config.max_reconnects + 1):
            headers = self._headers(accept="text/event-stream")
            if last_event_id is not None:
                headers["Last-Event-ID"] = last_event_id

            try:
                with self._client.stream(
                    "GET",
                    self._url(path),
                    headers=headers,
                    timeout=self._config.stream_timeout,
                ) as response:
                    response.raise_for_status()
                    for event in self._parse_sse(response.iter_lines(), run_id):
                        if event.event_id and event.event_id in seen_event_ids:
                            continue
                        if event.event_id:
                            seen_event_ids.add(event.event_id)
                            last_event_id = event.event_id
                        saw_event = True
                        yield event
                        if event.event_type in {
                            HermesEventType.COMPLETED,
                            HermesEventType.RUN_COMPLETED,
                            HermesEventType.FAILED,
                            HermesEventType.RUN_FAILED,
                            HermesEventType.CANCELLED,
                            HermesEventType.RUN_CANCELLED,
                        }:
                            return
            except httpx.TimeoutException as exc:
                if attempt >= self._config.max_reconnects:
                    self._logger.error(
                        "Hermes stream timeout run_id=%s attempts=%s",
                        run_id,
                        attempt + 1,
                    )
                    raise HermesTimeoutError(
                        f"Hermes event stream timed out: {exc}"
                    ) from exc
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_reconnects:
                    if saw_event:
                        self._logger.error(
                            "Hermes partial stream run_id=%s attempts=%s",
                            run_id,
                            attempt + 1,
                        )
                        raise HermesPartialStreamError(
                            f"Hermes event stream disconnected: {exc}"
                        ) from exc
                    raise HermesNetworkError(
                        f"Hermes event stream failed: {exc}"
                    ) from exc
                self._logger.warning(
                    "Reconnecting Hermes stream run_id=%s attempt=%s",
                    run_id,
                    attempt + 1,
                )
                continue

            if attempt >= self._config.max_reconnects:
                self._logger.error(
                    "Hermes stream ended without terminal event run_id=%s",
                    run_id,
                )
                raise HermesUnknownTerminalState(
                    "Hermes event stream ended without a terminal event"
                )

    def cancel(self, run_id: str) -> None:
        path = self._config.cancel_path.format(run_id=run_id)
        try:
            response = self._client.post(
                self._url(path),
                headers=self._headers(),
                timeout=self._config.cancellation_timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HermesTimeoutError(
                f"Hermes cancellation timed out: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise HermesNetworkError(f"Hermes cancellation failed: {exc}") from exc

    def health(self) -> dict[str, Any]:
        try:
            response = self._client.get(
                self._url(self._config.health_path),
                headers=self._headers(),
                timeout=self._config.submission_timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "status": "unhealthy",
                "available": False,
                "error": str(exc),
            }

        if not isinstance(body, dict):
            return {
                "status": "unhealthy",
                "available": False,
                "error": "Hermes health response must be an object",
            }

        status = body.get("status", "healthy")
        available = body.get(
            "available",
            status in {"healthy", "ok", "online"},
        )
        return {**body, "status": status, "available": bool(available)}

    def _url(self, path: str) -> str:
        return f"{self._config.endpoint.rstrip('/')}/{path.lstrip('/')}"

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        headers = {"Accept": accept}
        if accept == "application/json":
            headers["Content-Type"] = "application/json"
        if self._config.auth_token:
            headers["Authorization"] = f"Bearer {self._config.auth_token}"
        return headers

    @classmethod
    def _parse_sse(
        cls,
        lines: Iterable[str | bytes],
        default_run_id: str,
    ) -> Iterator[HermesEvent]:
        event_name: str | None = None
        event_id: str | None = None
        data_lines: list[str] = []

        for line in lines:
            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if line == "":
                if data_lines:
                    event = cls._event_from_sse(
                        event_name,
                        event_id,
                        "\n".join(data_lines),
                        default_run_id,
                    )
                    if event is not None:
                        yield event
                event_name = None
                event_id = None
                data_lines = []
                continue

            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("id:"):
                event_id = line[3:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if data_lines:
            event = cls._event_from_sse(
                event_name,
                event_id,
                "\n".join(data_lines),
                default_run_id,
            )
            if event is not None:
                yield event

    @staticmethod
    def _event_from_sse(
        event_name: str | None,
        event_id: str | None,
        data: str,
        default_run_id: str,
    ) -> HermesEvent | None:
        if data == "[DONE]":
            return None

        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Hermes SSE data was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Hermes SSE event payload must be an object")

        nested = payload.get("data")
        if isinstance(nested, dict):
            payload = nested

        raw_type = (
            event_name
            or payload.get("type")
            or payload.get("event_type")
            or HermesEventType.PROGRESS.value
        )
        try:
            event_type = HermesEventType(raw_type)
        except ValueError:
            event_type = HermesEventType.PROGRESS

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        if raw_type not in {member.value for member in HermesEventType}:
            metadata = {**metadata, "raw_event_type": raw_type}

        delta = payload.get("delta")
        if isinstance(delta, dict):
            delta = delta.get("text") or delta.get("content")

        return HermesEvent(
            run_id=payload.get("run_id", default_run_id),
            event_type=event_type,
            event_id=payload.get("event_id", event_id),
            message=payload.get("message"),
            progress=payload.get("progress"),
            result=payload.get("result"),
            error=payload.get("error"),
            approval_id=payload.get("approval_id"),
            delta=delta if isinstance(delta, str) else None,
            tool_name=payload.get("tool_name"),
            tool_call_id=payload.get("tool_call_id"),
            metadata=metadata,
        )
