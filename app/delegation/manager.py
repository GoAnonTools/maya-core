"""In-memory delegation lifecycle manager."""

from collections.abc import Callable
from typing import Any

from app.delegation.models import (
    DelegationEvent,
    DelegationRequest,
    DelegationStatus,
)


EventSink = Callable[[DelegationEvent], None]


class DelegationManager:
    """Accept requests and track their provider-neutral lifecycle."""

    _TRANSITIONS = {
        DelegationStatus.PENDING: {
            DelegationStatus.STARTED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.STARTED: {
            DelegationStatus.PROGRESS,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.PROGRESS: {
            DelegationStatus.PROGRESS,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.COMPLETED: set(),
        DelegationStatus.FAILED: set(),
        DelegationStatus.CANCELLED: set(),
    }

    def __init__(self, event_sink: EventSink | None = None) -> None:
        self._requests: dict[str, DelegationRequest] = {}
        self._statuses: dict[str, DelegationStatus] = {}
        self._events: dict[str, list[DelegationEvent]] = {}
        self._event_sink = event_sink

    def accept(self, request: DelegationRequest) -> DelegationEvent:
        """Accept a new request and emit its pending event."""
        if not request.delegation_id.strip():
            raise ValueError("delegation_id must not be empty")

        if not request.task.strip():
            raise ValueError("task must not be empty")

        if request.delegation_id in self._requests:
            raise ValueError(
                f"Delegation already exists: {request.delegation_id}"
            )

        self._requests[request.delegation_id] = request
        self._statuses[request.delegation_id] = DelegationStatus.PENDING
        self._events[request.delegation_id] = []

        return self._emit(
            request.delegation_id,
            DelegationStatus.PENDING,
            message="Delegation accepted.",
        )

    def start(
        self,
        delegation_id: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark an accepted delegation as started."""
        return self._transition(
            delegation_id,
            DelegationStatus.STARTED,
            message=message,
            metadata=metadata,
        )

    def progress(
        self,
        delegation_id: str,
        progress: float,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Record progress for a started delegation."""
        if not 0.0 <= progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")

        return self._transition(
            delegation_id,
            DelegationStatus.PROGRESS,
            message=message,
            progress=progress,
            metadata=metadata,
        )

    def complete(
        self,
        delegation_id: str,
        result: Any = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark a delegation as completed."""
        return self._transition(
            delegation_id,
            DelegationStatus.COMPLETED,
            message=message,
            result=result,
            progress=1.0,
            metadata=metadata,
        )

    def fail(
        self,
        delegation_id: str,
        error: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark a delegation as failed with a provider-neutral error."""
        if not error.strip():
            raise ValueError("error must not be empty")

        return self._transition(
            delegation_id,
            DelegationStatus.FAILED,
            message=message,
            error=error,
            metadata=metadata,
        )

    def cancel(
        self,
        delegation_id: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Cancel a pending or active delegation."""
        return self._transition(
            delegation_id,
            DelegationStatus.CANCELLED,
            message=message,
            metadata=metadata,
        )

    def get_request(self, delegation_id: str) -> DelegationRequest:
        """Return an accepted delegation request."""
        self._require(delegation_id)
        return self._requests[delegation_id]

    def get_status(self, delegation_id: str) -> DelegationStatus:
        """Return the current lifecycle status."""
        self._require(delegation_id)
        return self._statuses[delegation_id]

    def events(self, delegation_id: str) -> list[DelegationEvent]:
        """Return a copy of the lifecycle event history."""
        self._require(delegation_id)
        return list(self._events[delegation_id])

    def _transition(
        self,
        delegation_id: str,
        status: DelegationStatus,
        *,
        message: str | None = None,
        progress: float | None = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        current = self._require(delegation_id)

        if status not in self._TRANSITIONS[current]:
            raise ValueError(
                f"Invalid delegation transition: {current.value} -> "
                f"{status.value}"
            )

        return self._emit(
            delegation_id,
            status,
            message=message,
            progress=progress,
            result=result,
            error=error,
            metadata=metadata,
        )

    def _emit(
        self,
        delegation_id: str,
        status: DelegationStatus,
        *,
        message: str | None = None,
        progress: float | None = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        event = DelegationEvent(
            delegation_id=delegation_id,
            status=status,
            message=message,
            progress=progress,
            result=result,
            error=error,
            metadata=dict(metadata or {}),
        )
        self._statuses[delegation_id] = status
        self._events[delegation_id].append(event)

        if self._event_sink is not None:
            self._event_sink(event)

        return event

    def _require(self, delegation_id: str) -> DelegationStatus:
        if delegation_id not in self._requests:
            raise KeyError(f"Unknown delegation: {delegation_id}")

        return self._statuses[delegation_id]
