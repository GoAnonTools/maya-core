"""Worker execution boundaries used by Maya Core."""

from app.workers.base import Worker
from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.registry import WorkerRegistry

__all__ = [
    "OpenAICompatibleWorker",
    "MinistralWorker",
    "Worker",
    "WorkerCapability",
    "WorkerRegistry",
    "WorkerRole",
]


def __getattr__(name):
    if name == "OpenAICompatibleWorker":
        from app.workers.openai_compatible import OpenAICompatibleWorker

        return OpenAICompatibleWorker

    if name == "MinistralWorker":
        from app.workers.ministral import MinistralWorker

        return MinistralWorker

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
