"""Declarative approval and operation policy for delegation."""

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Any


class ApprovalRequirement(str, Enum):
    """Rules describing when an operation requires approval."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    REQUIRED_FOR_MUTATIONS = "required_for_mutations"
    REQUIRED_FOR_NETWORK = "required_for_network"


class OperationScope(str, Enum):
    """Whether an operation only reads or changes external state."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"


class HermesRecommendation(str, Enum):
    """Recommendation returned by the disabled-by-default Hermes policy."""

    CANDIDATE = "candidate"
    LOCAL = "local"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class HermesPolicyDecision:
    """A recommendation that does not select or execute a worker."""

    recommendation: HermesRecommendation
    eligible_for_hermes: bool
    hermes_enabled: bool
    approval_required: bool = False
    reason: str = ""
    missing_permissions: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)


class HermesDelegationPolicy:
    """Recommend Hermes eligibility without performing delegation.

    The policy is deliberately separate from routing. It never selects a
    worker, submits a job, approves an operation, or changes the default
    executor.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    @classmethod
    def from_environment(cls) -> "HermesDelegationPolicy":
        """Load the opt-in flag; Hermes is disabled unless explicitly enabled."""
        return cls(
            enabled=os.getenv("MAYA_HERMES_ENABLED", "false").lower()
            in {"1", "true", "yes"}
        )

    def recommend(
        self,
        task: str,
        *,
        task_category: str | None = None,
        dangerous: bool = False,
        requires_approval: bool = False,
        granted_permissions: frozenset[str] = frozenset(),
        required_permissions: frozenset[str] = frozenset(),
    ) -> HermesPolicyDecision:
        """Return a recommendation only; never execute or approve work."""
        if not isinstance(task, str) or not task.strip():
            return self._local("empty task")

        missing = frozenset(required_permissions - granted_permissions)
        if missing:
            return HermesPolicyDecision(
                recommendation=HermesRecommendation.LOCAL,
                eligible_for_hermes=False,
                hermes_enabled=self.enabled,
                reason="required permissions are not granted",
                missing_permissions=missing,
            )

        if dangerous or requires_approval:
            return HermesPolicyDecision(
                recommendation=HermesRecommendation.APPROVAL_REQUIRED,
                eligible_for_hermes=False,
                hermes_enabled=self.enabled,
                approval_required=True,
                reason="task requires approval before delegation",
            )

        category = self._category(task, task_category)
        if category in {"coding", "research"}:
            if not self.enabled:
                return HermesPolicyDecision(
                    recommendation=HermesRecommendation.CANDIDATE,
                    eligible_for_hermes=False,
                    hermes_enabled=False,
                    reason=(
                        "task is a Hermes candidate, but Hermes is disabled; "
                        "local fallback remains effective"
                    ),
                    metadata={"effective_target": "local"},
                )

            return HermesPolicyDecision(
                recommendation=HermesRecommendation.CANDIDATE,
                eligible_for_hermes=True,
                hermes_enabled=True,
                reason=f"{category} task is eligible for Hermes",
                metadata={"task_category": category},
            )

        if category == "unknown":
            return self._local("task category is unknown")

        return self._local("task is suitable for local execution")

    def _local(self, reason: str) -> HermesPolicyDecision:
        return HermesPolicyDecision(
            recommendation=HermesRecommendation.LOCAL,
            eligible_for_hermes=False,
            hermes_enabled=self.enabled,
            reason=reason,
        )

    @staticmethod
    def _category(task: str, requested: str | None) -> str:
        if requested:
            normalized = requested.strip().lower()
            if normalized in {"coding", "research", "conversation", "simple"}:
                return normalized
            return "unknown"

        text = task.lower()
        if any(
            marker in text
            for marker in (
                "code",
                "coding",
                "repository",
                "bug",
                "implement",
                "refactor",
                "script",
            )
        ):
            return "coding"
        if any(
            marker in text
            for marker in (
                "research",
                "investigate",
                "sources",
                "literature",
                "compare",
            )
        ):
            return "research"
        if "?" in text or text.startswith(("what ", "who ", "when ", "why ", "how ")):
            return "conversation"
        return "unknown"


@dataclass(frozen=True)
class DelegationPolicy:
    """Describe delegation permissions without executing them."""

    approval_requirement: ApprovalRequirement = (
        ApprovalRequirement.REQUIRED_FOR_MUTATIONS
    )
    allowed_operations: frozenset[str] = field(default_factory=frozenset)
    read_only_operations: frozenset[str] = field(default_factory=frozenset)
    mutating_operations: frozenset[str] = field(default_factory=frozenset)
    network_allowed: bool = False

    def is_operation_allowed(self, operation: str) -> bool:
        """Return whether an operation is declared as allowed."""
        return operation in self.allowed_operations

    def operation_scope(self, operation: str) -> OperationScope:
        """Return the declared scope for an operation."""
        if operation in self.read_only_operations:
            return OperationScope.READ_ONLY

        if operation in self.mutating_operations:
            return OperationScope.MUTATING

        raise ValueError(f"Operation has no declared scope: {operation}")

    def allows_network(self) -> bool:
        """Return whether delegated operations may use the network."""
        return self.network_allowed

    def requires_approval(
        self,
        operation: str,
        *,
        uses_network: bool = False,
    ) -> bool:
        """Describe whether approval is required for an operation.

        This method only evaluates policy. It does not request, grant, or
        enforce approval.
        """
        if not self.is_operation_allowed(operation):
            raise PermissionError(f"Operation is not allowed: {operation}")

        scope = self.operation_scope(operation)

        if uses_network and not self.network_allowed:
            raise PermissionError("Network access is not allowed")

        if self.approval_requirement == ApprovalRequirement.REQUIRED:
            return True

        if self.approval_requirement == ApprovalRequirement.REQUIRED_FOR_MUTATIONS:
            return scope == OperationScope.MUTATING

        if self.approval_requirement == ApprovalRequirement.REQUIRED_FOR_NETWORK:
            return uses_network

        return False
