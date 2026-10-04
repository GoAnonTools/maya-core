"""Provider-neutral delegation lifecycle boundary."""

from app.delegation.models import (
    DelegationEvent,
    DelegationRequest,
    DelegationStatus,
)
from app.delegation.policy import (
    ApprovalRequirement,
    DelegationPolicy,
    OperationScope,
)

__all__ = [
    "DelegationEvent",
    "DelegationManager",
    "DelegationRequest",
    "DelegationStatus",
    "ApprovalRequirement",
    "DelegationPolicy",
    "OperationScope",
]


def __getattr__(name):
    if name == "DelegationManager":
        from app.delegation.manager import DelegationManager

        return DelegationManager

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
