"""Deterministic mapping from task categories to required capabilities."""

from app.routing.classification import TaskCategory


TASK_CAPABILITY_MAP: dict[TaskCategory, frozenset[str]] = {
    TaskCategory.CONVERSATION: frozenset({"conversation"}),
    TaskCategory.CODING: frozenset({"coding"}),
    TaskCategory.RESEARCH: frozenset({"research"}),
    TaskCategory.TOOL_USE: frozenset({"tool_call_proposal"}),
    TaskCategory.FILE_OPERATION: frozenset({"filesystem_read"}),
}


def required_capabilities_for(category: TaskCategory) -> frozenset[str]:
    """Return capabilities associated with a task category."""
    return TASK_CAPABILITY_MAP[category]
