"""Declarative approval and operation policy for delegation."""

from dataclasses import dataclass, field
from enum import Enum


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
