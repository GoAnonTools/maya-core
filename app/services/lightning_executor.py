"""Execution abstractions for the Lightning service boundary."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator
from uuid import uuid4

from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


@dataclass
class LightningSession:
    """Execution state owned by the in-memory executor."""

    execution_id: str
    session_id: str
    job: LightningJob
    cancelled: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class ExecutorCapabilities:
    """Provider-neutral description of executor support."""

    supported_task_categories: frozenset[str] = frozenset()
    required_permissions: frozenset[str] = frozenset()
    available: bool = False
    version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def task_categories(self) -> frozenset[str]:
        """Short alias for consumers that call them task categories."""
        return self.supported_task_categories


class LightningExecutor(ABC):
    """Interface for Lightning job execution backends."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return a stable name for the executor implementation."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this executor can accept execution work."""

    def capabilities(self) -> ExecutorCapabilities:
        """Describe support without changing routing or activating execution."""
        return ExecutorCapabilities(
            available=self.is_available(),
            metadata={"backend": self.backend_name},
        )

    @abstractmethod
    def submit(self, job: LightningJob) -> str:
        """Accept a job and return its execution identifier."""

    @abstractmethod
    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        """Yield lifecycle events for an execution."""

    @abstractmethod
    def cancel(self, execution_id: str) -> None:
        """Cancel an active execution."""

    @abstractmethod
    def active_jobs(self) -> int:
        """Return the number of non-terminal executions."""

    @abstractmethod
    def get_session(self, execution_id: str) -> LightningSession:
        """Return execution state for service-level inspection."""


class InMemoryLightningExecutor(LightningExecutor):
    """Deterministic executor used by local development and current tests."""

    @property
    def backend_name(self) -> str:
        return "in_memory"

    def __init__(self) -> None:
        self._sessions: dict[str, LightningSession] = {}
        self._available = True

    def is_available(self) -> bool:
        return self._available

    def capabilities(self) -> ExecutorCapabilities:
        return ExecutorCapabilities(
            supported_task_categories=frozenset({"general"}),
            required_permissions=frozenset(),
            available=self.is_available(),
            version="1",
            metadata={
                "backend": self.backend_name,
                "execution": "in_memory",
                "default": True,
                "version": "1",
            },
        )

    def submit(self, job: LightningJob) -> str:
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

    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        session = self.get_session(execution_id)

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
            result={"backend": self.backend_name, "execution_id": execution_id},
        )

    def cancel(self, execution_id: str) -> None:
        session = self.get_session(execution_id)

        if session.terminal:
            raise ValueError("Cannot cancel a terminal Lightning session")

        session.cancelled = True

    def active_jobs(self) -> int:
        return sum(
            not session.terminal for session in self._sessions.values()
        )

    def get_session(self, execution_id: str) -> LightningSession:
        try:
            return self._sessions[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown Lightning execution: {execution_id}"
            ) from exc

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
            metadata={"backend": self.backend_name},
        )
