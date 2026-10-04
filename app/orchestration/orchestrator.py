"""Execution orchestration without routing policy."""

from collections.abc import Iterator
from dataclasses import dataclass
import logging
from typing import Any
from uuid import uuid4

from app.routing import BasicRoutingPolicy, RoutingContext, RoutingPolicy
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


class Orchestrator:
    """Execute normalized requests through a configured default worker."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        default_worker_id: str,
        routing_policy: RoutingPolicy | None = None,
    ) -> None:
        self._worker_registry = worker_registry
        self._default_worker_id = default_worker_id
        self._routing_policy = (
            routing_policy
            if routing_policy is not None
            else BasicRoutingPolicy()
        )

    def _decision(self, request: NormalizedRequest):
        request_metadata = request.metadata or {}
        required_capabilities = request_metadata.get(
            "required_capabilities",
            (),
        )
        routing_context = RoutingContext(
            request=request,
            worker_registry=self._worker_registry,
            default_worker_id=self._default_worker_id,
            required_capabilities=frozenset(required_capabilities),
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
