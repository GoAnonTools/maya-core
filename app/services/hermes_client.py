"""Injectable client contract for a future Hermes Agent API."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from app.services.hermes_protocol import HermesEvent, HermesJob


class HermesClient(ABC):
    """Client boundary consumed by ``HermesExecutor``.

    Implementations may later use HTTP, a local service socket, or another
    transport. This interface itself performs no I/O.
    """

    @abstractmethod
    def submit(self, job: HermesJob) -> str:
        """Submit a Hermes job and return its Hermes ``run_id``."""

    @abstractmethod
    def stream_events(self, run_id: str) -> Iterator[HermesEvent]:
        """Yield normalized Hermes events for a run."""

    @abstractmethod
    def cancel(self, run_id: str) -> None:
        """Request cancellation of a Hermes run."""

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return client/backend health without exposing secrets."""
