"""Worker routing policy contracts and the current default-only policy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.workers.capabilities import WorkerCapability
from app.workers.registry import WorkerRegistry

if TYPE_CHECKING:
    from app.orchestration.orchestrator import NormalizedRequest


@dataclass(frozen=True)
class RoutingContext:
    """Inputs available to a routing policy."""

    request: NormalizedRequest
    worker_registry: WorkerRegistry
    default_worker_id: str
    required_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoutingDecision:
    """Explainable result of a routing policy evaluation."""

    worker_id: str
    reason: str
    capability: WorkerCapability
    metadata: dict[str, Any] = field(default_factory=dict)


class RoutingPolicy(ABC):
    """Interface for policies that select an executable worker."""

    @abstractmethod
    def decide(self, context: RoutingContext) -> RoutingDecision:
        """Return an explainable worker selection decision."""


class BasicRoutingPolicy(RoutingPolicy):
    """Resolve every request to the configured default worker.

    This is intentionally not intent classification or worker switching. It
    evaluates capability metadata only and keeps the executable default
    worker as the sole selectable target.
    """

    def decide(self, context: RoutingContext) -> RoutingDecision:
        request_metadata = dict(context.request.metadata or {})
        required_capabilities = frozenset(context.required_capabilities)
        capabilities = context.worker_registry.list_capabilities()
        capability = next(
            (
                item
                for item in capabilities
                if item.worker_id == context.default_worker_id
            ),
            None,
        )

        if capability is None:
            raise LookupError(
                "Default worker has no registered capability metadata: "
                f"{context.default_worker_id}"
            )

        if not capability.availability:
            raise RuntimeError(
                "Default worker is unavailable: "
                f"{context.default_worker_id}"
            )

        missing_capabilities = required_capabilities.difference(
            capability.capabilities
        )

        if missing_capabilities:
            raise LookupError(
                "Default worker does not provide required capabilities: "
                + ", ".join(sorted(missing_capabilities))
            )

        return RoutingDecision(
            worker_id=capability.worker_id,
            reason=(
                "default executable worker matches required capabilities"
            ),
            capability=capability,
            metadata={
                "request_metadata": request_metadata,
                "required_capabilities": sorted(required_capabilities),
                "matched_capabilities": sorted(
                    required_capabilities.intersection(
                        capability.capabilities
                    )
                ),
                "considered_workers": [
                    item.worker_id for item in capabilities
                ],
            },
        )
