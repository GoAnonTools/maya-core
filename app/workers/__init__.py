"""Worker execution boundaries used by Maya Core."""

from app.workers.base import Worker
from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.registry import WorkerRegistry
from app.workers.specialist import SpecialistWorker

__all__ = [
    "OpenAICompatibleWorker",
    "MinistralWorker",
    "LightningSpecialistWorker",
    "LightningRemoteClient",
    "LightningTransport",
    "Worker",
    "WorkerCapability",
    "WorkerRegistry",
    "WorkerRole",
    "SpecialistWorker",
]


def __getattr__(name):
    if name == "OpenAICompatibleWorker":
        from app.workers.openai_compatible import OpenAICompatibleWorker

        return OpenAICompatibleWorker

    if name == "MinistralWorker":
        from app.workers.ministral import MinistralWorker

        return MinistralWorker

    if name == "LightningSpecialistWorker":
        from app.workers.lightning import LightningSpecialistWorker

        return LightningSpecialistWorker

    if name in {"LightningRemoteClient", "LightningTransport"}:
        from app.workers.lightning_transport import (
            LightningRemoteClient,
            LightningTransport,
        )

        return {
            "LightningRemoteClient": LightningRemoteClient,
            "LightningTransport": LightningTransport,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
