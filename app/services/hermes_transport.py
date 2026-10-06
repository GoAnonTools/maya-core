"""Transport seam for the Phase 1 Hermes client.

No HTTP or external transport is implemented in this phase. A future client
can implement ``HermesTransport`` and be wrapped by ``TransportHermesClient``.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from app.services.hermes_client import HermesClient
from app.services.hermes_protocol import HermesEvent, HermesJob


class HermesTransport(ABC):
    """Low-level transport contract for Hermes Agent communication."""

    @abstractmethod
    def submit(self, job: HermesJob) -> str:
        """Send a job and return a Hermes run ID."""

    @abstractmethod
    def stream_events(self, run_id: str) -> Iterator[HermesEvent]:
        """Read the Hermes event stream for a run."""

    @abstractmethod
    def cancel(self, run_id: str) -> None:
        """Send a cancellation request for a run."""

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return transport health."""


class TransportHermesClient(HermesClient):
    """Adapt an injected transport to the HermesClient interface."""

    def __init__(self, transport: HermesTransport) -> None:
        self._transport = transport

    def submit(self, job: HermesJob) -> str:
        return self._transport.submit(job)

    def stream_events(self, run_id: str) -> Iterator[HermesEvent]:
        yield from self._transport.stream_events(run_id)

    def cancel(self, run_id: str) -> None:
        self._transport.cancel(run_id)

    def health(self) -> dict[str, Any]:
        return self._transport.health()
