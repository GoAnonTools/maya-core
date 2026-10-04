"""Placeholder execution boundary for the Coding Specialist."""

from collections.abc import Iterator
from typing import Any

from app.delegation.models import (
    DelegationEvent,
    DelegationRequest,
    DelegationStatus,
)
from app.workers.capabilities import WorkerCapability
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)
from app.workers.lightning_transport import LightningRemoteClient
from app.workers.specialist import SpecialistWorker
from app.workers.specialists.coding import CodingSpecialistProfile


class CodingSpecialistWorker(SpecialistWorker):
    """Non-executing Coding Specialist contract implementation.

    This class models the worker boundary only. It performs no repository,
    filesystem, process, network, or model operations.
    """

    def __init__(
        self,
        profile: CodingSpecialistProfile | None = None,
        lightning_client: LightningRemoteClient | None = None,
    ) -> None:
        self._profile = profile or CodingSpecialistProfile()
        self._lightning_client = lightning_client
        self._requests: dict[str, DelegationRequest] = {}
        self._executions: dict[str, str] = {}
        self._cancelled: set[str] = set()

    def capability(self) -> WorkerCapability:
        """Return the Coding Specialist's provider-neutral capabilities."""
        return self._profile.capability_metadata()

    def submit(self, request: DelegationRequest) -> str:
        """Accept a request already bound to the Coding Specialist profile."""
        self._validate_request(request)
        if request.delegation_id in self._requests:
            raise ValueError(
                f"Delegation already submitted: {request.delegation_id}"
            )

        self._requests[request.delegation_id] = request
        if self._lightning_client is not None:
            job = self._create_lightning_job(request)
            self._executions[request.delegation_id] = (
                self._lightning_client.submit(job)
            )
        return request.delegation_id

    def start(self) -> None:
        """Start the injected Lightning client, when configured."""
        if self._lightning_client is not None:
            self._lightning_client.start()

    def stream_events(self, delegation_id: str) -> Iterator[DelegationEvent]:
        """Yield placeholder lifecycle events for a submitted delegation."""
        self._require_request(delegation_id)

        if self._lightning_client is not None:
            execution_id = self._executions[delegation_id]
            for event in self._lightning_client.stream_events(execution_id):
                yield self._to_delegation_event(event)
            return

        if delegation_id in self._cancelled:
            yield DelegationEvent(
                delegation_id=delegation_id,
                status=DelegationStatus.CANCELLED,
                message="Coding Specialist placeholder cancelled.",
            )
            return

        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.STARTED,
            message="Coding Specialist placeholder started.",
        )
        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.PROGRESS,
            progress=0.5,
            message="Coding Specialist execution is not connected.",
        )

        if delegation_id in self._cancelled:
            yield DelegationEvent(
                delegation_id=delegation_id,
                status=DelegationStatus.CANCELLED,
                message="Coding Specialist placeholder cancelled.",
            )
            return

        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            progress=1.0,
            message="Coding Specialist placeholder completed.",
            result={"placeholder": True},
        )

    def cancel(self, delegation_id: str) -> None:
        """Mark a submitted placeholder delegation as cancelled."""
        self._require_request(delegation_id)
        self._cancelled.add(delegation_id)
        if self._lightning_client is not None:
            self._lightning_client.cancel(self._executions[delegation_id])

    def shutdown(self) -> None:
        """Close the injected Lightning client, when configured."""
        if self._lightning_client is not None:
            self._lightning_client.shutdown()

    def complete(self, delegation_id: str, result: Any = None) -> DelegationEvent:
        """Create a provider-neutral completion event."""
        self._require_request(delegation_id)
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            progress=1.0,
            result=result,
        )

    def fail(self, delegation_id: str, error: str) -> DelegationEvent:
        """Create a provider-neutral failure event."""
        self._require_request(delegation_id)
        if not error.strip():
            raise ValueError("error must not be empty")
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.FAILED,
            error=error,
        )

    def _validate_request(self, request: DelegationRequest) -> None:
        if not request.specialist_id:
            raise ValueError("request must be bound to a specialist profile")
        if request.specialist_id != self._profile.worker_id:
            raise ValueError(
                f"request is bound to a different specialist: "
                f"{request.specialist_id}"
            )
        if request.specialist_role != self._profile.role:
            raise ValueError("request specialist role does not match the profile")

        required = set(request.required_capabilities)
        missing = required - self._profile.capabilities
        if missing:
            raise ValueError(
                "Coding Specialist is missing required capabilities: "
                + ", ".join(sorted(missing))
            )

        bound = set(request.specialist_capabilities)
        if not self._profile.capabilities.issubset(bound):
            raise ValueError("request specialist capability snapshot is incomplete")

    def _create_lightning_job(self, request: DelegationRequest) -> LightningJob:
        metadata = dict(request.metadata)
        permissions = request.specialist_metadata.get("required_permissions", ())
        return LightningJob(
            delegation_id=request.delegation_id,
            request_id=request.request_id,
            session_id=request.session_id,
            workspace=metadata.get("workspace"),
            capabilities=request.required_capabilities,
            permissions=frozenset(permissions),
            metadata={
                "specialist_id": request.specialist_id,
                "specialist_role": request.specialist_role.value,
                "specialist_metadata": dict(request.specialist_metadata),
                **metadata,
            },
        )

    @staticmethod
    def _to_delegation_event(event: LightningEvent) -> DelegationEvent:
        status_by_type = {
            LightningEventType.STARTED: DelegationStatus.STARTED,
            LightningEventType.PROGRESS: DelegationStatus.PROGRESS,
            LightningEventType.COMPLETED: DelegationStatus.COMPLETED,
            LightningEventType.FAILED: DelegationStatus.FAILED,
            LightningEventType.CANCELLED: DelegationStatus.CANCELLED,
        }
        return DelegationEvent(
            delegation_id=event.delegation_id,
            status=status_by_type[event.event_type],
            progress=event.progress,
            message=event.message,
            result=event.result,
            error=event.error,
            metadata={"source": "lightning", **dict(event.metadata)},
        )

    def _require_request(self, delegation_id: str) -> DelegationRequest:
        try:
            return self._requests[delegation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown delegation: {delegation_id}") from exc
