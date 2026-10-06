"""Provider-neutral delegation lifecycle models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.workers.capabilities import WorkerRole


class DelegationStatus(str, Enum):
    """Lifecycle states emitted by the delegation manager."""

    PENDING = "pending"
    RUNNING = "running"
    STARTED = "started"
    PROGRESS = "progress"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DelegationEventType(str, Enum):
    """Provider-neutral event categories."""

    LIFECYCLE = "lifecycle"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class PendingApproval:
    """Approval request awaiting a Maya Core decision."""

    delegation_id: str
    approval_id: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class DelegationRequest:
    """A provider-neutral request to perform delegated work."""

    delegation_id: str
    task: str
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    session_id: str | None = None
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    selected_worker: dict[str, Any] = field(default_factory=dict)
    specialist_id: str | None = None
    specialist_role: WorkerRole | None = None
    specialist_capabilities: frozenset[str] = field(
        default_factory=frozenset
    )
    specialist_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DelegationEvent:
    """A structured lifecycle event for a delegation request."""

    delegation_id: str
    status: DelegationStatus
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    message: str | None = None
    progress: float | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_type: DelegationEventType = DelegationEventType.LIFECYCLE
