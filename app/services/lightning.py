"""In-memory Lightning service skeleton.

This service models remote specialist job lifecycle locally. It deliberately
does not perform model execution or use a network transport.
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


@dataclass
class LightningSession:
    """In-memory execution session for a submitted Lightning job."""

    execution_id: str
    session_id: str
    job: LightningJob
    cancelled: bool = False
    terminal: bool = False


class LightningService:
    """Minimal in-memory service for Lightning protocol jobs."""

    def __init__(self) -> None:
        self._sessions: dict[str, LightningSession] = {}
        self._healthy = True

    def submit(self, job: LightningJob) -> str:
        """Create an in-memory delegation session for a job."""
        if not job.delegation_id.strip():
            raise ValueError("delegation_id must not be empty")

        execution_id = f"lightning-execution-{uuid4()}"
        session_id = job.session_id or f"lightning-session-{uuid4()}"
        self._sessions[execution_id] = LightningSession(
            execution_id=execution_id,
            session_id=session_id,
            job=job,
        )
        return execution_id

    def stream_events(self, execution_id: str):
        """Emit deterministic in-memory lifecycle events for a job."""
        session = self._get_session(execution_id)

        yield self._event(session, LightningEventType.STARTED)

        if session.cancelled:
            session.terminal = True
            yield self._event(session, LightningEventType.CANCELLED)
            return

        yield self._event(
            session,
            LightningEventType.PROGRESS,
            progress=0.5,
            message="In-memory execution progress.",
        )

        if session.cancelled:
            session.terminal = True
            yield self._event(session, LightningEventType.CANCELLED)
            return

        session.terminal = True
        yield self._event(
            session,
            LightningEventType.COMPLETED,
            progress=1.0,
            result={"backend": "in_memory", "execution_id": execution_id},
        )

    def cancel(self, execution_id: str) -> None:
        """Mark an active in-memory session as cancelled."""
        session = self._get_session(execution_id)

        if session.terminal:
            raise ValueError("Cannot cancel a terminal Lightning session")

        session.cancelled = True

    def health(self) -> dict[str, Any]:
        """Return service health without probing external systems."""
        active_jobs = sum(
            not session.terminal for session in self._sessions.values()
        )
        return {
            "service": "lightning",
            "status": "healthy" if self._healthy else "unhealthy",
            "backend": "in_memory",
            "active_jobs": active_jobs,
        }

    def get_session(self, execution_id: str) -> LightningSession:
        """Return an in-memory session for inspection."""
        return self._get_session(execution_id)

    def _event(
        self,
        session: LightningSession,
        event_type: LightningEventType,
        *,
        progress: float | None = None,
        message: str | None = None,
        result: Any = None,
    ) -> LightningEvent:
        return LightningEvent(
            delegation_id=session.job.delegation_id,
            event_type=event_type,
            request_id=session.job.request_id,
            session_id=session.session_id,
            progress=progress,
            message=message,
            result=result,
            metadata={"backend": "in_memory"},
        )

    def _get_session(self, execution_id: str) -> LightningSession:
        try:
            return self._sessions[execution_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Lightning execution: {execution_id}") from exc
