"""Registry for executable worker instances."""

from typing import Any

from app.workers.base import Worker
from app.workers.capabilities import WorkerCapability
from app.workers.specialist import SpecialistWorker


class WorkerRegistry:
    """Store and retrieve workers by stable worker ID.

    The registry is deliberately passive. It does not select a worker,
    inspect requests, or decide how work should be routed.
    """

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}
        self._specialist_workers: dict[str, SpecialistWorker] = {}
        self._capabilities: dict[str, WorkerCapability] = {}

    def register(
        self,
        worker_id: str,
        worker: Worker,
        capability: WorkerCapability | None = None,
    ) -> None:
        """Register a worker under ``worker_id``.

        Worker IDs are unique within a registry. Re-registering an existing
        ID is rejected so accidental replacement cannot happen silently.
        """
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id must not be empty")

        if not isinstance(worker, Worker):
            raise TypeError("worker must implement the Worker contract")

        if capability is not None:
            if not isinstance(capability, WorkerCapability):
                raise TypeError(
                    "capability must be a WorkerCapability instance"
                )

            if capability.worker_id != worker_id:
                raise ValueError(
                    "capability.worker_id must match worker_id"
                )

        if worker_id in self._workers:
            raise ValueError(f"Worker already registered: {worker_id}")

        if capability is not None:
            self.register_capability(capability)

        self._workers[worker_id] = worker

    def register_capability(self, capability: WorkerCapability) -> None:
        """Register capability metadata without registering a worker."""
        if not isinstance(capability, WorkerCapability):
            raise TypeError("capability must be a WorkerCapability instance")

        if not capability.worker_id.strip():
            raise ValueError("capability.worker_id must not be empty")

        if capability.worker_id in self._capabilities:
            raise ValueError(
                f"Capability already registered: {capability.worker_id}"
            )

        self._capabilities[capability.worker_id] = capability

    def register_specialist(
        self,
        worker_id: str,
        worker: SpecialistWorker,
        capability: WorkerCapability | None = None,
    ) -> None:
        """Register an explicitly supplied specialist worker separately."""
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id must not be empty")

        if not isinstance(worker, SpecialistWorker):
            raise TypeError(
                "worker must implement the SpecialistWorker contract"
            )

        worker_capability = capability or worker.capability()

        if worker_capability.worker_id != worker_id:
            raise ValueError(
                "capability.worker_id must match worker_id"
            )

        if worker_id in self._workers or worker_id in self._specialist_workers:
            raise ValueError(f"Worker already registered: {worker_id}")

        self.register_capability(worker_capability)
        self._specialist_workers[worker_id] = worker

    def get(self, worker_id: str) -> Worker:
        """Return the worker registered under ``worker_id``."""
        try:
            return self._workers[worker_id]
        except KeyError as exc:
            raise KeyError(f"Unknown worker: {worker_id}") from exc

    def get_specialist(self, worker_id: str) -> SpecialistWorker:
        """Return an explicitly registered specialist worker."""
        try:
            return self._specialist_workers[worker_id]
        except KeyError as exc:
            raise KeyError(f"Unknown specialist worker: {worker_id}") from exc

    def list_workers(self) -> list[str]:
        """Return registered worker IDs in registration order."""
        return list(self._workers)

    def get_capability(self, worker_id: str) -> WorkerCapability:
        """Return capability metadata for a registered worker."""
        try:
            return self._capabilities[worker_id]
        except KeyError as exc:
            raise KeyError(f"No capability metadata: {worker_id}") from exc

    def list_capabilities(self) -> list[WorkerCapability]:
        """Return attached capability metadata in registration order."""
        return list(self._capabilities.values())

    def is_available(self, worker_id: str) -> bool:
        """Return whether a worker is registered and available.

        Workers may optionally expose an ``is_available`` method or boolean
        attribute. Workers without that optional capability are considered
        available when registered.
        """
        worker = self._workers.get(worker_id)

        if worker is None:
            worker = self._specialist_workers.get(worker_id)

        if worker is None:
            return False

        capability = self._capabilities.get(worker_id)

        if capability is not None and not capability.availability:
            return False

        availability: Any = getattr(worker, "is_available", True)

        if callable(availability):
            return bool(availability())

        return bool(availability)
