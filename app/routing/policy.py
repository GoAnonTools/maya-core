"""Worker routing policy contracts and the current default-only policy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.workers.capabilities import WorkerCapability
from app.workers.capabilities import WorkerRole
from app.workers.registry import WorkerRegistry
from app.routing.classification import TaskClassification

if TYPE_CHECKING:
    from app.orchestration.orchestrator import NormalizedRequest


class RoutingFailure(LookupError):
    """Explainable failure to satisfy a routing capability requirement."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        worker_id: str,
        required_capabilities: frozenset[str],
        missing_capabilities: frozenset[str],
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.worker_id = worker_id
        self.required_capabilities = required_capabilities
        self.missing_capabilities = missing_capabilities


@dataclass(frozen=True)
class RoutingContext:
    """Inputs available to a routing policy."""

    request: NormalizedRequest
    worker_registry: WorkerRegistry
    default_worker_id: str
    required_capabilities: frozenset[str] = frozenset()
    classification: TaskClassification | None = None
    task_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoutingDecision:
    """Explainable result of a routing policy evaluation."""

    worker_id: str
    reason: str
    capability: WorkerCapability
    metadata: dict[str, Any] = field(default_factory=dict)
    reason_code: str = "unspecified"
    fallback_used: bool = False


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
        requested_capabilities = frozenset(context.required_capabilities)
        required_capabilities = requested_capabilities or frozenset(
            {"conversational"}
        )
        capabilities = context.worker_registry.list_capabilities()
        default_capability = next(
            (
                item
                for item in capabilities
                if item.worker_id == context.default_worker_id
            ),
            None,
        )

        if default_capability is None:
            raise RoutingFailure(
                "Default worker has no registered capability metadata: "
                f"{context.default_worker_id}",
                reason_code="default_capability_missing",
                worker_id=context.default_worker_id,
                required_capabilities=required_capabilities,
                missing_capabilities=required_capabilities,
            )

        specialist = self._specialist_worker(
            capabilities,
            context,
            required_capabilities,
        )

        if specialist is not None:
            return self._decision(
                specialist,
                request_metadata,
                requested_capabilities,
                required_capabilities,
                capabilities,
                "specialist capability requires delegation handoff",
                "specialist_delegation_required",
            )

        if "conversational" in required_capabilities:
            preferred = self._preferred_conversational_worker(
                capabilities,
                context,
                required_capabilities,
            )

            if preferred is not None:
                return self._decision(
                    preferred,
                    request_metadata,
                    requested_capabilities,
                    required_capabilities,
                    capabilities,
                    "preferred conversational worker matches required capabilities",
                    "conversation_preferred",
                )

        if not self._matches(default_capability, required_capabilities):
            missing_capabilities = required_capabilities.difference(
                default_capability.capabilities
            )
            raise RoutingFailure(
                "Default worker does not provide required capabilities: "
                + ", ".join(sorted(missing_capabilities)),
                reason_code="required_capabilities_missing",
                worker_id=default_capability.worker_id,
                required_capabilities=required_capabilities,
                missing_capabilities=frozenset(missing_capabilities),
            )

        if not default_capability.availability or not context.worker_registry.is_available(
            default_capability.worker_id
        ):
            raise RuntimeError(
                "Default worker is unavailable: "
                f"{context.default_worker_id}"
            )

        return self._decision(
            default_capability,
            request_metadata,
            requested_capabilities,
            required_capabilities,
            capabilities,
            (
                "existing default worker used as conversational fallback"
                if "conversational" in required_capabilities
                else "default executable worker matches required capabilities"
            ),
            (
                "default_fallback"
                if "conversational" in required_capabilities
                else "default_capability_match"
            ),
            "conversational" in required_capabilities,
        )

    def _specialist_worker(
        self,
        capabilities: list[WorkerCapability],
        context: RoutingContext,
        required_capabilities: frozenset[str],
    ) -> WorkerCapability | None:
        specialists = [
            capability
            for capability in capabilities
            if capability.role == WorkerRole.SPECIALIST
            and required_capabilities.intersection(
                capability.capabilities
            )
        ]

        if not specialists:
            return None

        for capability in specialists:
            if (
                capability.availability
                and self._matches(capability, required_capabilities)
            ):
                return capability

        unavailable = specialists[0]
        raise RoutingFailure(
            "Required specialist capabilities are unavailable: "
            + ", ".join(sorted(required_capabilities)),
            reason_code="specialist_unavailable",
            worker_id=unavailable.worker_id,
            required_capabilities=required_capabilities,
            missing_capabilities=frozenset(),
        )

    def _preferred_conversational_worker(
        self,
        capabilities: list[WorkerCapability],
        context: RoutingContext,
        required_capabilities: frozenset[str],
    ) -> WorkerCapability | None:
        for capability in capabilities:
            preferred_for = capability.metadata.get("preferred_for", [])

            if (
                capability.worker_id != context.default_worker_id
                and capability.role.value == "conversational"
                and "conversational" in preferred_for
                and capability.availability
                and context.worker_registry.is_available(capability.worker_id)
                and self._matches(capability, required_capabilities)
            ):
                return capability

        return None

    @staticmethod
    def _matches(
        capability: WorkerCapability,
        required_capabilities: frozenset[str],
    ) -> bool:
        return required_capabilities.issubset(capability.capabilities)

    @staticmethod
    def _decision(
        capability: WorkerCapability,
        request_metadata: dict[str, Any],
        requested_capabilities: frozenset[str],
        required_capabilities: frozenset[str],
        capabilities: list[WorkerCapability],
        reason: str,
        reason_code: str,
        fallback_used: bool = False,
    ) -> RoutingDecision:
        return RoutingDecision(
            worker_id=capability.worker_id,
            reason=reason,
            capability=capability,
            metadata={
                "request_metadata": request_metadata,
                "requested_capabilities": sorted(requested_capabilities),
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
            reason_code=reason_code,
            fallback_used=fallback_used,
        )
