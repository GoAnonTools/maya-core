from typing import Any

from app.settings import load_settings


CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


def build_chat_completion_payload(
    context: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    """Build an OpenAI-compatible chat completion payload."""
    message = context.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Request context message must not be empty")

    maya = context.get("maya")
    if not isinstance(maya, dict):
        raise ValueError("Request context must include maya identity data")

    identity = maya.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("Request context must include a Maya identity")

    model = route.get("model")
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


def build_chat_completion_request(
    context: dict[str, Any],
    route: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare the request target and body without making a network call."""
    current_settings = settings if settings is not None else load_settings()
    services = _as_mapping(current_settings.get("services"))
    model_service = _as_mapping(services.get("model"))

    return {
        "base_url": model_service.get("base_url"),
        "path": CHAT_COMPLETIONS_PATH,
        "payload": build_chat_completion_payload(context, route),
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
