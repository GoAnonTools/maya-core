"""Provider-neutral models for the Phase 1 Hermes adapter boundary."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HermesEventType(str, Enum):
    """Event kinds exposed by Hermes, including legacy normalized names."""

    # Legacy normalized names retained for existing clients and tests.
    STARTED = "started"
    PROGRESS = "progress"
    APPROVAL_REQUIRED = "approval_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Realistic Hermes Agent lifecycle names.
    RUN_STARTED = "run.started"
    MESSAGE_DELTA = "message.delta"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    APPROVAL_REQUEST = "approval.request"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"


@dataclass(frozen=True)
class HermesJob:
    """Hermes-facing representation of a delegated Lightning job."""

    delegation_id: str
    request_id: str | None = None
    session_id: str | None = None
    task: str | None = None
    workspace: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HermesEvent:
    """A normalized or raw-lifecycle event received from Hermes."""

    run_id: str
    event_type: HermesEventType
    event_id: str | None = None
    message: str | None = None
    progress: float | None = None
    result: Any = None
    error: str | None = None
    approval_id: str | None = None
    delta: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HermesRunMapping:
    """Correlation between Maya/Lightning execution and Hermes run IDs."""

    execution_id: str
    run_id: str
    delegation_id: str
    session_id: str
