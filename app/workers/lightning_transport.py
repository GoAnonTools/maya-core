"""Transport-independent client boundary for remote Lightning jobs."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from app.workers.lightning_protocol import (
    LightningEvent,
    LightningJob,
    LightningWorkerConfig,
)


class LightningTransport(ABC):
    """Pluggable transport contract for remote job communication."""

    @abstractmethod
    def connect(self, config: LightningWorkerConfig) -> None:
        """Open the transport connection."""

    @abstractmethod
    def submit(self, job: LightningJob) -> str:
        """Submit a job and return its remote execution ID."""

    @abstractmethod
    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        """Yield events for a remote execution."""

    @abstractmethod
    def cancel(self, execution_id: str) -> None:
        """Request cancellation of a remote execution."""

    @abstractmethod
    def close(self) -> None:
        """Close the transport connection."""


class LightningRemoteClient:
    """Manage remote Lightning jobs through an injected transport."""

    def __init__(
        self,
        transport: LightningTransport,
        config: LightningWorkerConfig,
    ) -> None:
        self._transport = transport
        self._config = config
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        """Connect the configured transport."""
        if not self._connected:
            self._transport.connect(self._config)
            self._connected = True

    def submit(self, job: LightningJob) -> str:
        """Submit a job after ensuring the transport is connected."""
        self._require_connected()
        return self._transport.submit(job)

    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        """Forward the transport's structured event stream."""
        self._require_connected()
        yield from self._transport.stream_events(execution_id)

    def cancel(self, execution_id: str) -> None:
        """Forward a cancellation request to the transport."""
        self._require_connected()
        self._transport.cancel(execution_id)

    def shutdown(self) -> None:
        """Close the transport and mark the client disconnected."""
        if self._connected:
            self._transport.close()
            self._connected = False

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Lightning remote client is not connected")
