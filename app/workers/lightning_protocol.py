"""Provider-neutral protocol models for remote specialist execution.

These models describe a possible remote job protocol only. They do not make
network calls or connect to a worker implementation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import os
from typing import Any


class LightningEventType(str, Enum):
    """Lifecycle event types for a remote specialist job."""

    SUBMITTED = "submitted"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class LightningWorkerConfig:
    """Configuration placeholders for a future remote worker connection."""

    endpoint: str | None = None
    workspace: str | None = None
    deployment: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> "LightningWorkerConfig":
        return cls(
            endpoint=os.getenv("MAYA_LIGHTNING_ENDPOINT"),
            workspace=os.getenv("MAYA_LIGHTNING_WORKSPACE"),
            deployment=os.getenv("MAYA_LIGHTNING_DEPLOYMENT"),
            capabilities=_csv_environment("MAYA_LIGHTNING_CAPABILITIES"),
            permissions=_csv_environment("MAYA_LIGHTNING_PERMISSIONS"),
            enabled=os.getenv("MAYA_LIGHTNING_ENABLED", "false").lower()
            in {"1", "true", "yes"},
        )


@dataclass(frozen=True)
class LightningJob:
    """Provider-neutral description of a delegated remote specialist job."""

    delegation_id: str
    request_id: str | None
    session_id: str | None
    workspace: str | None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    status: LightningEventType = LightningEventType.SUBMITTED
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LightningEvent:
    """Structured lifecycle or progress event for a Lightning job."""

    delegation_id: str
    event_type: LightningEventType
    request_id: str | None = None
    session_id: str | None = None
    progress: float | None = None
    message: str | None = None
    result: Any = None
    error: str | None = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)


def _csv_environment(name: str) -> frozenset[str]:
    value = os.getenv(name, "")
    return frozenset(item.strip() for item in value.split(",") if item.strip())
