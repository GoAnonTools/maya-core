"""Ministral worker backed by the existing OpenAI-compatible model client."""

import os
from collections.abc import Callable, Iterator
from typing import Any

from app.model_client import send_prompt, stream_prompt
from app.settings import load_settings
from app.workers.openai_compatible import OpenAICompatibleWorker


DEFAULT_MINISTRAL_MODEL = "mistralai/Ministral-8B-Instruct-2410"


class MinistralWorker(OpenAICompatibleWorker):
    """Execute requests against a configured Ministral endpoint.

    The worker owns only its execution target. It does not decide when it
    should be used; that remains the responsibility of routing policy.
    """

    def __init__(
        self,
        send_prompt_fn: Callable[..., dict[str, Any]] = send_prompt,
        stream_prompt_fn: Callable[..., Iterator[str]] = stream_prompt,
        settings: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            send_prompt_fn=send_prompt_fn,
            stream_prompt_fn=stream_prompt_fn,
        )
        self.route = build_ministral_route(settings)

    def execute(
        self,
        context: dict[str, Any],
        route: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return super().execute(context, self.route)

    def stream(
        self,
        context: dict[str, Any],
        route: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        yield from super().stream(context, self.route)

    def is_available(self) -> bool:
        """Report whether a Ministral endpoint is configured."""
        return bool(self.route.get("endpoint") or self.route.get("base_url"))


def build_ministral_route(
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a provider-neutral route from config and environment values."""
    current_settings = settings if settings is not None else load_settings()
    services = _as_mapping(current_settings.get("services"))
    configured = _as_mapping(services.get("ministral"))

    model = os.getenv(
        "MAYA_MINISTRAL_MODEL",
        configured.get("model", DEFAULT_MINISTRAL_MODEL),
    )
    base_url = os.getenv(
        "MAYA_MINISTRAL_BASE_URL",
        configured.get("base_url"),
    )
    endpoint = os.getenv(
        "MAYA_MINISTRAL_ENDPOINT",
        configured.get("endpoint") or base_url,
    )

    return {
        "mode": configured.get("mode", "online"),
        "model": model,
        "provider": configured.get("provider", "openai_compatible"),
        "base_url": base_url,
        "endpoint": endpoint,
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
