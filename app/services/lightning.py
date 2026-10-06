"""Lightning service boundary backed by an injectable executor."""

from typing import Any, Iterator

from app.services.lightning_executor import (
    ExecutorCapabilities,
    InMemoryLightningExecutor,
    LightningExecutor,
    LightningSession,
)
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


class LightningService:
    """Protocol service that delegates execution to a LightningExecutor."""

    def __init__(self, executor: LightningExecutor | None = None) -> None:
        self._executor = executor or InMemoryLightningExecutor()

    @property
    def executor(self) -> LightningExecutor:
        """Return the executor behind this service boundary."""
        return self._executor

    def submit(self, job: LightningJob) -> str:
        """Accept a Lightning job through the configured executor."""
        return self._executor.submit(job)

    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        """Forward the executor's lifecycle event stream."""
        return self._executor.stream_events(execution_id)

    def cancel(self, execution_id: str) -> None:
        """Forward cancellation to the configured executor."""
        self._executor.cancel(execution_id)

    def capabilities(self) -> ExecutorCapabilities:
        """Return executor capabilities without selecting an execution path."""
        return self._executor.capabilities()

    def health(self) -> dict[str, Any]:
        """Return service health and executor availability."""
        available = self._executor.is_available()
        return {
            "service": "lightning",
            "status": "healthy" if available else "unhealthy",
            "backend": self._executor.backend_name,
            "available": available,
            "active_jobs": self._executor.active_jobs(),
        }

    def get_session(self, execution_id: str) -> LightningSession:
        """Return executor session state for the protocol adapter."""
        return self._executor.get_session(execution_id)

    def _event(
        self,
        session: LightningSession,
        event_type: LightningEventType,
        *,
        progress: float | None = None,
        message: str | None = None,
        result: Any = None,
    ) -> LightningEvent:
        """Build an event for service subclasses that customize streaming."""
        return LightningEvent(
            delegation_id=session.job.delegation_id,
            event_type=event_type,
            request_id=session.job.request_id,
            session_id=session.session_id,
            progress=progress,
            message=message,
            result=result,
            metadata={"backend": self._executor.backend_name},
        )
