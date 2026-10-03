from typing import Any

from app.router import select_model


def send_prompt(
    context: dict[str, Any],
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a request context through the selected model client.

    Transport is intentionally not implemented yet. The returned metadata
    makes the current connection state explicit without making a network call.
    """
    selected_route = select_model() if route is None else route
    payload = build_chat_completion_payload(context, selected_route)
    endpoint = selected_route.get("endpoint")

    if endpoint is None:
        return {
            "status": "unavailable",
            "model": selected_route.get("model"),
            "message": "No model endpoint is configured; prompt was not sent.",
            "request": payload,
        }

    return {
        "status": "not_connected",
        "model": selected_route.get("model"),
        "message": "Model client transport is not implemented; prompt was not sent.",
        "request": payload,
    }


def build_chat_completion_payload(
    context: dict[str, Any],
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the OpenAI-compatible request body without sending it."""
    message = context.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Request context message must not be empty")

    maya = context.get("maya")
    if not isinstance(maya, dict):
        raise ValueError("Request context must include maya identity data")

    identity = maya.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("Request context must include a Maya identity")

    selected_route = select_model() if route is None else route
    model = selected_route.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Model route must include a model name")

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": f"You are {identity}.",
            },
            {
                "role": "user",
                "content": message.strip(),
            },
        ],
    }
