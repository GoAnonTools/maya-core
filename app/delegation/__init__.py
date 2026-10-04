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
from app.delegation.profile_binding import bind_specialist_profile

__all__ = [
    "DelegationEvent",
    "DelegationManager",
    "DelegationRequest",
    "DelegationStatus",
    "ApprovalRequirement",
    "DelegationPolicy",
    "OperationScope",
    "bind_specialist_profile",
]


def __getattr__(name):
    if name == "DelegationManager":
        from app.delegation.manager import DelegationManager

        return DelegationManager

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
