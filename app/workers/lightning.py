"""Placeholder Lightning specialist worker adapter.

This module defines only the worker boundary and in-memory lifecycle behavior.
It intentionally performs no Lightning, network, process, Docker, or SSH work.
"""

from dataclasses import dataclass, field
import os
from typing import Any

from app.delegation.models import DelegationEvent, DelegationRequest, DelegationStatus
from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.specialist import SpecialistWorker


@dataclass(frozen=True)
class LightningWorkerConfig:
    """Connection placeholders for a future Lightning implementation."""

    endpoint: str | None = None
    workspace: str | None = None
    deployment: str | None = None
    enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> "LightningWorkerConfig":
        return cls(
            endpoint=os.getenv("MAYA_LIGHTNING_ENDPOINT"),
            workspace=os.getenv("MAYA_LIGHTNING_WORKSPACE"),
            deployment=os.getenv("MAYA_LIGHTNING_DEPLOYMENT"),
            enabled=os.getenv("MAYA_LIGHTNING_ENABLED", "false").lower()
            in {"1", "true", "yes"},
        )


class LightningSpecialistWorker(SpecialistWorker):
    """In-memory placeholder for a future Lightning specialist worker."""

    def __init__(
        self,
        config: LightningWorkerConfig | None = None,
    ) -> None:
        self.config = config or LightningWorkerConfig.from_environment()
        self._started = False
        self._requests: dict[str, DelegationRequest] = {}
        self._cancelled: set[str] = set()

    def capability(self) -> WorkerCapability:
        return WorkerCapability(
            worker_id="lightning-specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Lightning specialist worker",
            capabilities=frozenset(
                {
                    "coding",
                    "research",
                    "tool_call_proposal",
                    "filesystem_read",
                }
            ),
            availability=False,
            metadata={
                "execution": "placeholder",
                "provider": "lightning",
            },
        )

    def start(self) -> None:
        self._started = True

    def submit(self, request: DelegationRequest) -> str:
        if not self._started:
            raise RuntimeError("Lightning specialist worker is not started")

        self._requests[request.delegation_id] = request
        return request.delegation_id

    def stream_events(self, delegation_id: str):
        if delegation_id not in self._requests:
            yield self.fail(
                delegation_id,
                "Delegation was not submitted to the Lightning worker.",
            )
            return

        yield DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.STARTED,
            metadata={"source": "lightning-placeholder"},
        )

        if delegation_id in self._cancelled:
            yield DelegationEvent(
                delegation_id=delegation_id,
                status=DelegationStatus.CANCELLED,
                metadata={"source": "lightning-placeholder"},
            )
            return

        yield self.fail(
            delegation_id,
            "Lightning specialist execution is not implemented.",
        )

    def cancel(self, delegation_id: str) -> None:
        self._cancelled.add(delegation_id)

    def complete(self, delegation_id: str, result: Any = None) -> DelegationEvent:
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.COMPLETED,
            result=result,
            metadata={"source": "lightning-placeholder"},
        )

    def fail(self, delegation_id: str, error: str) -> DelegationEvent:
        return DelegationEvent(
            delegation_id=delegation_id,
            status=DelegationStatus.FAILED,
            error=error,
            metadata={"source": "lightning-placeholder"},
        )

    def shutdown(self) -> None:
        self._started = False
        self._requests.clear()
        self._cancelled.clear()
