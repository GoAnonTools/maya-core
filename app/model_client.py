from typing import Any

import httpx

from app.providers.openai_compatible import (
    build_chat_completion_payload,
    build_chat_completion_request,
    send_chat_completion,
)
from app.router import select_model


def send_prompt(
    context: dict[str, Any],
    route: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Send a request context through the selected model client.

    Transport is intentionally not implemented yet. The returned metadata
    makes the current connection state explicit without making a network call.
    """
    selected_route = select_model() if route is None else route
    request = build_chat_completion_request(context, selected_route)
    payload = request["payload"]
    endpoint = selected_route.get("endpoint") or request["base_url"]
    if selected_route.get("mode") == "offline":
        endpoint = None

    if endpoint is None:
        return {
            "status": "unavailable",
            "model": selected_route.get("model"),
            "message": "No model endpoint is configured; prompt was not sent.",
            "request": payload,
        }

    if client is not None:
        return {
            "status": "ok",
            "model": selected_route.get("model"),
            "message": send_chat_completion(request, client),
            "request": payload,
        }

    return {
        "status": "not_connected",
        "model": selected_route.get("model"),
        "message": "Model client transport is not implemented; prompt was not sent.",
        "request": payload,
    }
