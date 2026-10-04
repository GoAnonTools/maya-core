"""Worker adapter for the existing OpenAI-compatible model flow."""

from collections.abc import Callable, Iterator
from typing import Any

from app.model_client import send_prompt, stream_prompt
from app.workers.base import Worker


class OpenAICompatibleWorker(Worker):
    """Delegate worker execution to the existing model client.

    This adapter intentionally contains no routing or provider-selection
    logic. The caller supplies the route exactly as it did before the worker
    boundary was introduced.
    """

    def __init__(
        self,
        send_prompt_fn: Callable[..., dict[str, Any]] = send_prompt,
        stream_prompt_fn: Callable[..., Iterator[str]] = stream_prompt,
    ) -> None:
        self._send_prompt = send_prompt_fn
        self._stream_prompt = stream_prompt_fn

    def execute(
        self,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> dict[str, Any]:
        return self._send_prompt(context, route)

    def stream(
        self,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> Iterator[str]:
        yield from self._stream_prompt(context, route)
