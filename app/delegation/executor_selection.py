"""Explicit, opt-in executor selection for delegated work."""

from dataclasses import dataclass, field
from typing import Any

from app.delegation.models import DelegationRequest
from app.delegation.policy import (
    HermesDelegationPolicy,
    HermesPolicyDecision,
    HermesRecommendation,
)
from app.services.lightning_executor import (
    ExecutorCapabilities,
    InMemoryLightningExecutor,
    LightningExecutor,
)


@dataclass(frozen=True)
class ExecutorSelection:
    """Result of an explicit executor selection decision."""

    executor: LightningExecutor | None
    target: str
    blocked: bool = False
    reason: str = ""
    trace: dict[str, Any] = field(default_factory=dict)


class ExecutorSelector:
    """Contract for selecting an executor without changing global routing."""

    def select(
        self,
        request: DelegationRequest,
        *,
        task_category: str | None = None,
        approval_granted: bool = False,
    ) -> ExecutorSelection:
        raise NotImplementedError


class OptInHermesExecutorSelector(ExecutorSelector):
    """Choose Hermes only when policy, approval, and capabilities allow it."""

    def __init__(
        self,
        hermes_executor: LightningExecutor,
        fallback_executor: LightningExecutor | None = None,
        policy: HermesDelegationPolicy | None = None,
    ) -> None:
        self.hermes_executor = hermes_executor
        self.fallback_executor = fallback_executor or InMemoryLightningExecutor()
        self.policy = policy or HermesDelegationPolicy()

    def select(
        self,
        request: DelegationRequest,
        *,
        task_category: str | None = None,
        approval_granted: bool = False,
    ) -> ExecutorSelection:
        metadata = request.metadata
        category = task_category or metadata.get("task_category")
        dangerous = bool(metadata.get("dangerous", False))
        requires_approval = bool(metadata.get("requires_approval", False))
        required_permissions = frozenset(
            metadata.get("required_permissions", ())
        )
        granted_permissions = frozenset(
            metadata.get("granted_permissions", ())
        )

        decision = self.policy.recommend(
            request.task,
            task_category=category,
            dangerous=dangerous,
            requires_approval=requires_approval,
            granted_permissions=granted_permissions,
            required_permissions=required_permissions,
        )

        if decision.approval_required and not approval_granted:
            return self._blocked(decision)

        if decision.approval_required and approval_granted:
            decision = self.policy.recommend(
                request.task,
                task_category=category,
                granted_permissions=granted_permissions,
                required_permissions=required_permissions,
            )

        hermes_capabilities = self.hermes_executor.capabilities()
        trace = self._trace(decision, hermes_capabilities)
        category_name = decision.metadata.get("task_category", category)

        if (
            decision.eligible_for_hermes
            and hermes_capabilities.available
            and isinstance(category_name, str)
            and category_name in hermes_capabilities.supported_task_categories
        ):
            return ExecutorSelection(
                executor=self.hermes_executor,
                target=self.hermes_executor.backend_name,
                reason="Hermes policy and capabilities allow execution",
                trace={**trace, "selected": self.hermes_executor.backend_name},
            )

        fallback_capabilities = self.fallback_executor.capabilities()
        return ExecutorSelection(
            executor=self.fallback_executor,
            target=self.fallback_executor.backend_name,
            reason=self._fallback_reason(
                decision,
                hermes_capabilities,
                category_name,
            ),
            trace={
                **trace,
                "fallback": self.fallback_executor.backend_name,
                "fallback_available": fallback_capabilities.available,
                "selected": self.fallback_executor.backend_name,
            },
        )

    def _blocked(self, decision: HermesPolicyDecision) -> ExecutorSelection:
        return ExecutorSelection(
            executor=None,
            target="none",
            blocked=True,
            reason=decision.reason,
            trace={
                "policy_recommendation": decision.recommendation.value,
                "approval_required": True,
                "selected": None,
            },
        )

    @staticmethod
    def _trace(
        decision: HermesPolicyDecision,
        capabilities: ExecutorCapabilities,
    ) -> dict[str, Any]:
        return {
            "policy_recommendation": decision.recommendation.value,
            "policy_eligible": decision.eligible_for_hermes,
            "hermes_enabled": decision.hermes_enabled,
            "hermes_available": capabilities.available,
            "hermes_task_categories": sorted(
                capabilities.supported_task_categories
            ),
            "hermes_capability_version": capabilities.version,
        }

    @staticmethod
    def _fallback_reason(
        decision: HermesPolicyDecision,
        capabilities: ExecutorCapabilities,
        category: Any,
    ) -> str:
        if decision.recommendation == HermesRecommendation.LOCAL:
            return decision.reason
        if not decision.hermes_enabled:
            return "Hermes is disabled; using local fallback"
        if not capabilities.available:
            return "Hermes is unavailable; using local fallback"
        if category not in capabilities.supported_task_categories:
            return "Hermes lacks the requested capability; using local fallback"
        return "Hermes was not selected; using local fallback"
