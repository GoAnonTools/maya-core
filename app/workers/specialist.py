"""Provider-neutral specialist worker execution contract."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from app.delegation.models import DelegationEvent, DelegationRequest
from app.workers.capabilities import WorkerCapability


class SpecialistWorker(ABC):
    """Contract for workers that execute delegated specialist tasks.

    Implementations decide how work is executed. This interface does not
    choose workers, manage lifecycle storage, or impose a provider/runtime.
    """

    def start(self) -> None:
        """Start worker resources; the default contract is a no-op."""

    def shutdown(self) -> None:
        """Release worker resources; the default contract is a no-op."""

    @abstractmethod
    def capability(self) -> WorkerCapability:
        """Return provider-neutral capability metadata for this worker."""

    @abstractmethod
    def submit(self, request: DelegationRequest) -> str:
        """Submit a delegated task and return its execution identifier."""

    @abstractmethod
    def stream_events(self, delegation_id: str) -> Iterator[DelegationEvent]:
        """Yield structured events for a delegated task."""

    @abstractmethod
    def cancel(self, delegation_id: str) -> None:
        """Request cancellation of a delegated task."""

    @abstractmethod
    def complete(
        self,
        delegation_id: str,
        result: Any = None,
    ) -> DelegationEvent:
        """Report successful completion of a delegated task."""

    @abstractmethod
    def fail(
        self,
        delegation_id: str,
        error: str,
    ) -> DelegationEvent:
        """Report failure of a delegated task."""
