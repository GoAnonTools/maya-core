"""In-memory delegation lifecycle manager."""

from collections.abc import Callable
from typing import Any

from app.delegation.models import (
    DelegationEvent,
    DelegationRequest,
    DelegationStatus,
)
from app.workers.registry import WorkerRegistry
from app.workers.specialist import SpecialistWorker


EventSink = Callable[[DelegationEvent], None]


class DelegationManager:
    """Accept requests and track their provider-neutral lifecycle."""

    _TRANSITIONS = {
        DelegationStatus.PENDING: {
            DelegationStatus.STARTED,
            DelegationStatus.FAILED,
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

    def __init__(
        self,
        event_sink: EventSink | None = None,
        worker_registry: WorkerRegistry | None = None,
    ) -> None:
        self._requests: dict[str, DelegationRequest] = {}
        self._statuses: dict[str, DelegationStatus] = {}
        self._events: dict[str, list[DelegationEvent]] = {}
        self._event_sink = event_sink
        self._worker_registry = worker_registry
        self._active_workers: dict[
            str,
            tuple[SpecialistWorker, str],
        ] = {}

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
        active = self._active_workers.get(delegation_id)

        if active is not None:
            worker, execution_id = active
            worker.cancel(execution_id)

        return self._transition(
            delegation_id,
            DelegationStatus.CANCELLED,
            message=message,
            metadata=metadata,
        )

    def execute(
        self,
        request: DelegationRequest,
        worker_registry: WorkerRegistry | None = None,
    ) -> list[DelegationEvent]:
        """Execute a delegation through an explicitly registered specialist.

        This method coordinates lifecycle and event forwarding only. It does
        not create workers, launch processes, or select a route.
        """
        self.accept(request)
        registry = worker_registry or self._worker_registry
        worker_id = request.selected_worker.get("worker_id")

        if registry is None:
            self.fail(
                request.delegation_id,
                "No specialist worker registry is configured.",
            )
            return self.events(request.delegation_id)

        try:
            capability = registry.get_capability(worker_id)
        except (KeyError, TypeError):
            self.fail(
                request.delegation_id,
                f"No specialist capability is registered: {worker_id}",
            )
            return self.events(request.delegation_id)

        if capability.role.value != "specialist":
            self.fail(
                request.delegation_id,
                f"Selected worker is not specialist: {worker_id}",
            )
            return self.events(request.delegation_id)

        try:
            worker = registry.get_specialist(worker_id)
        except KeyError:
            self.fail(
                request.delegation_id,
                f"No executable specialist worker is registered: {worker_id}",
            )
            return self.events(request.delegation_id)

        if not capability.availability:
            self.fail(
                request.delegation_id,
                f"Specialist worker is unavailable: {worker_id}",
            )
            return self.events(request.delegation_id)

        self.start(request.delegation_id)

        try:
            execution_id = worker.submit(request)
            self._active_workers[request.delegation_id] = (
                worker,
                execution_id,
            )

            terminal = False

            for event in worker.stream_events(execution_id):
                self._forward_event(request.delegation_id, event)

                if event.status in {
                    DelegationStatus.COMPLETED,
                    DelegationStatus.FAILED,
                    DelegationStatus.CANCELLED,
                }:
                    terminal = True
                    break

            if not terminal and self.get_status(request.delegation_id) not in {
                DelegationStatus.CANCELLED,
                DelegationStatus.FAILED,
            }:
                self.fail(
                    request.delegation_id,
                    "Specialist worker ended without a terminal event.",
                )

        except Exception as exc:
            if self.get_status(request.delegation_id) not in {
                DelegationStatus.COMPLETED,
                DelegationStatus.FAILED,
                DelegationStatus.CANCELLED,
            }:
                self.fail(request.delegation_id, str(exc))
        finally:
            self._active_workers.pop(request.delegation_id, None)

        return self.events(request.delegation_id)

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

    def _forward_event(
        self,
        delegation_id: str,
        event: DelegationEvent,
    ) -> None:
        """Forward a worker event into the manager history and sink."""
        self._statuses[delegation_id] = event.status
        self._events[delegation_id].append(event)

        if self._event_sink is not None:
            self._event_sink(event)

    def _require(self, delegation_id: str) -> DelegationStatus:
        if delegation_id not in self._requests:
            raise KeyError(f"Unknown delegation: {delegation_id}")

        return self._statuses[delegation_id]
