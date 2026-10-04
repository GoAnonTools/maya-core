"""Bootstrap catalog for the currently supported worker set."""

from collections.abc import Callable, Iterator
from typing import Any

from app.model_client import send_prompt, stream_prompt
from app.workers import WorkerRegistry
from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.ministral import MinistralWorker
from app.workers.openai_compatible import OpenAICompatibleWorker


DEFAULT_WORKER_ID = "default"


def create_worker_catalog(
    send_prompt_fn: Callable[..., dict[str, Any]] = send_prompt,
    stream_prompt_fn: Callable[..., Iterator[str]] = stream_prompt,
) -> WorkerRegistry:
    """Create and register the currently configured worker set.

    This function only bootstraps worker instances and metadata. It does not
    inspect requests or make routing decisions.
    """
    registry = WorkerRegistry()
    worker = OpenAICompatibleWorker(
        send_prompt_fn=send_prompt_fn,
        stream_prompt_fn=stream_prompt_fn,
    )
    capability = WorkerCapability(
        worker_id=DEFAULT_WORKER_ID,
        role=WorkerRole.CONVERSATIONAL,
        display_name="OpenAI-compatible worker",
        capabilities=frozenset({"chat", "streaming", "conversational"}),
        availability=True,
        metadata={
            "execution": "openai-compatible",
            "fallback_for": ["conversational"],
        },
    )

    registry.register(
        DEFAULT_WORKER_ID,
        worker,
        capability=capability,
    )

    ministral_worker = MinistralWorker(
        send_prompt_fn=send_prompt_fn,
        stream_prompt_fn=stream_prompt_fn,
    )
    registry.register(
        "ministral",
        ministral_worker,
        capability=WorkerCapability(
            worker_id="ministral",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Ministral conversational worker",
            capabilities=frozenset({"chat", "streaming", "conversational"}),
            availability=ministral_worker.is_available(),
            metadata={
                "execution": "openai-compatible",
                "preferred_for": ["conversational"],
            },
        ),
    )

    registry.register_capability(
        WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Specialist worker",
            capabilities=frozenset({"specialized_tasks"}),
            availability=False,
            metadata={"execution": "not_registered"},
        )
    )

    registry.register_capability(
        WorkerCapability(
            worker_id="offline-fallback",
            role=WorkerRole.FALLBACK,
            display_name="Offline fallback worker",
            capabilities=frozenset({"offline", "fallback"}),
            availability=False,
            metadata={"execution": "not_registered"},
        )
    )

    return registry
