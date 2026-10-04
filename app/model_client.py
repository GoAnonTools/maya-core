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
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a request context through the selected model client."""

    selected_route = select_model() if route is None else route

    request = build_chat_completion_request(
        context,
        selected_route,
        settings=settings,
    )

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

    owns_client = False

    if client is None:
        client = httpx.Client(timeout=60.0)
        owns_client = True

    try:
        return {
            "status": "ok",
            "model": selected_route.get("model"),
            "message": send_chat_completion(request, client),
            "request": payload,
        }

    except RuntimeError as exc:
        return {
            "status": "unavailable",
            "model": selected_route.get("model"),
            "message": str(exc),
            "request": payload,
        }

    finally:
        if owns_client:
            client.close()
