"""Capability metadata for workers.

This module describes workers without selecting, invoking, or routing to them.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkerRole(str, Enum):
    """High-level role a worker advertises to the system."""

    CONVERSATIONAL = "conversational"
    SPECIALIST = "specialist"
    FALLBACK = "fallback"


@dataclass
class WorkerCapability:
    """Descriptive metadata for a registered worker.

    The fields are intentionally provider-neutral. ``metadata`` is reserved
    for additional descriptive values that future routing policy may inspect;
    this class itself does not interpret them.
    """

    worker_id: str
    role: WorkerRole
    display_name: str
    capabilities: frozenset[str] = field(default_factory=frozenset)
    availability: bool = True
    description: str | None = None
    priority: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
