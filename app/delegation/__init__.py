"""Provider-neutral delegation lifecycle boundary."""

from app.delegation.models import (
    DelegationEvent,
    DelegationEventType,
    DelegationRequest,
    DelegationStatus,
    PendingApproval,
)
from app.delegation.executor_selection import (
    ExecutorSelection,
    ExecutorSelector,
    OptInHermesExecutorSelector,
)
from app.delegation.policy import (
    ApprovalRequirement,
    DelegationPolicy,
    HermesDelegationPolicy,
    HermesPolicyDecision,
    HermesRecommendation,
    OperationScope,
)
from app.delegation.profile_binding import bind_specialist_profile

__all__ = [
    "DelegationEvent",
    "DelegationEventType",
    "DelegationManager",
    "DelegationRequest",
    "DelegationStatus",
    "PendingApproval",
    "ExecutorSelection",
    "ExecutorSelector",
    "OptInHermesExecutorSelector",
    "ApprovalRequirement",
    "DelegationPolicy",
    "HermesDelegationPolicy",
    "HermesPolicyDecision",
    "HermesRecommendation",
    "OperationScope",
    "bind_specialist_profile",
]


def __getattr__(name):
    if name == "DelegationManager":
        from app.delegation.manager import DelegationManager

        return DelegationManager

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
