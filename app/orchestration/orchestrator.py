"""Execution orchestration without routing policy."""

from collections.abc import Iterator
from dataclasses import dataclass
import logging
from typing import Any
from uuid import uuid4

from app.delegation.models import DelegationRequest
from app.routing import (
    BasicRoutingPolicy,
    DeterministicTaskClassifier,
    RoutingContext,
    RoutingPolicy,
    TaskClassifier,
    required_capabilities_for,
)
from app.workers.capabilities import WorkerRole
from app.workers.base import Worker
from app.workers.registry import WorkerRegistry


logger = logging.getLogger("maya.routing")


@dataclass(frozen=True)
class NormalizedRequest:
    """Request data prepared for worker execution.

    The route is carried through as already-resolved execution metadata. The
    orchestrator does not inspect it or make any decision from it.
    """

    context: dict[str, Any]
    route: dict[str, Any]
    metadata: dict[str, Any] | None = None
    request_id: str | None = None
    session_id: str | None = None


class Orchestrator:
    """Execute normalized requests through a configured default worker."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        default_worker_id: str,
        routing_policy: RoutingPolicy | None = None,
        task_classifier: TaskClassifier | None = None,
    ) -> None:
        self._worker_registry = worker_registry
        self._default_worker_id = default_worker_id
        self._routing_policy = (
            routing_policy
            if routing_policy is not None
            else BasicRoutingPolicy()
        )
        self._task_classifier = (
            task_classifier
            if task_classifier is not None
            else DeterministicTaskClassifier()
        )

    def _decision(self, request: NormalizedRequest):
        request_metadata = request.metadata or {}
        required_capabilities = request_metadata.get(
            "required_capabilities",
            (),
        )
        classification = self._task_classifier.classify(request)
        routing_context = RoutingContext(
            request=request,
            worker_registry=self._worker_registry,
            default_worker_id=self._default_worker_id,
            required_capabilities=frozenset(required_capabilities),
            classification=classification,
            task_capabilities=required_capabilities_for(
                classification.category
            ),
        )
        return self._routing_policy.decide(routing_context)

    @staticmethod
    def _request_id(request: NormalizedRequest) -> str:
        return (
            request.request_id
            or (request.metadata or {}).get("request_id")
            or str(uuid4())
        )

    def _log_decision(
        self,
        request: NormalizedRequest,
        decision,
    ) -> None:
        logger.info(
            "routing_decision",
            extra={
                "routing_decision": {
                    "request_id": self._request_id(request),
                    "required_capabilities": decision.metadata.get(
                        "required_capabilities",
                        [],
                    ),
                    "selected_worker_id": decision.worker_id,
                    "selected_role": decision.capability.role.value,
                    "reason_code": decision.reason_code,
                    "fallback_used": decision.fallback_used,
                }
            },
        )

    def prepare_delegation_request(
        self,
        request: NormalizedRequest,
    ) -> DelegationRequest:
        """Create a specialist handoff request without starting execution."""
        decision = self._decision(request)
        self._log_decision(request, decision)

        if decision.capability.role != WorkerRole.SPECIALIST:
            raise ValueError(
                "Delegation handoff requires a specialist routing decision"
            )

        request_id = self._request_id(request)
        task = request.context.get("message", "")

        if not isinstance(task, str) or not task.strip():
            raise ValueError("Delegation handoff requires a task message")

        selected_worker = {
            "worker_id": decision.capability.worker_id,
            "role": decision.capability.role.value,
            "display_name": decision.capability.display_name,
            "capabilities": sorted(decision.capability.capabilities),
            "metadata": dict(decision.capability.metadata),
        }

        return DelegationRequest(
            delegation_id=f"delegation-{uuid4()}",
            task=task.strip(),
            request_id=request_id,
            session_id=request.session_id,
            required_capabilities=frozenset(
                decision.metadata.get("required_capabilities", [])
            ),
            selected_worker=selected_worker,
            metadata={
                "reason_code": decision.reason_code,
                "routing_reason": decision.reason,
            },
        )

    def execute(self, request: NormalizedRequest) -> dict[str, Any]:
        """Execute a normalized request and return the worker result."""
        decision = self._decision(request)
        self._log_decision(request, decision)
        worker = self._worker_registry.get(decision.worker_id)
        return worker.execute(
            request.context,
            request.route,
        )

    def stream(self, request: NormalizedRequest) -> Iterator[str]:
        """Stream a normalized request through the default worker."""
        decision = self._decision(request)
        self._log_decision(request, decision)
        worker = self._worker_registry.get(decision.worker_id)
        yield from worker.stream(
            request.context,
            request.route,
        )
