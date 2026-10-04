"""Provider-neutral task classification metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.orchestration.orchestrator import NormalizedRequest


class TaskCategory(str, Enum):
    """Supported high-level task categories."""

    CONVERSATION = "conversation"
    CODING = "coding"
    RESEARCH = "research"
    TOOL_USE = "tool_use"
    FILE_OPERATION = "file_operation"


@dataclass(frozen=True)
class TaskClassification:
    """A provider-neutral classification result."""

    category: TaskCategory
    confidence: float = 1.0
    reason: str = "deterministic placeholder"
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskClassifier(ABC):
    """Interface for future task classification implementations."""

    @abstractmethod
    def classify(self, request: NormalizedRequest) -> TaskClassification:
        """Classify a normalized request without executing it."""


class DeterministicTaskClassifier(TaskClassifier):
    """Placeholder classifier with no model or provider dependency."""

    def classify(self, request: NormalizedRequest) -> TaskClassification:
        request_metadata = request.metadata or {}
        requested_category = request_metadata.get("task_category")

        if isinstance(requested_category, TaskCategory):
            return TaskClassification(
                category=requested_category,
                reason="explicit normalized request metadata",
                metadata={"source": "request_metadata"},
            )

        if isinstance(requested_category, str):
            try:
                category = TaskCategory(requested_category)
            except ValueError:
                category = None

            if category is not None:
                return TaskClassification(
                    category=category,
                    reason="explicit normalized request metadata",
                    metadata={"source": "request_metadata"},
                )

        return TaskClassification(
            category=TaskCategory.CONVERSATION,
            reason="deterministic placeholder default",
            metadata={"source": "placeholder"},
        )
