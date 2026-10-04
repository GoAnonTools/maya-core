from typing import Any

import httpx

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

    system_prompt = maya.get("system_prompt")

    if isinstance(system_prompt, str) and system_prompt.strip():
        system_content = system_prompt.strip()
    else:
        system_content = f"You are {identity}."

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_content,
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
        "base_url": (
            model_service.get("base_url")
            or route.get("base_url")
            or route.get("endpoint")
        ),
        "path": CHAT_COMPLETIONS_PATH,
        "payload": build_chat_completion_payload(context, route),
    }


def send_chat_completion(
    request: dict[str, Any],
    client: httpx.Client,
) -> str:
    """Send a prepared request with an injected HTTP client and parse its text."""
    base_url = request.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("OpenAI-compatible request must include a base URL")

    try:
        response = client.post(
            f"{base_url.rstrip('/')}{request['path']}",
            json=request["payload"],
        )
        response.raise_for_status()

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Model service unavailable: {exc}"
        ) from exc

    return parse_chat_completion_response(response.json())


def parse_chat_completion_response(response: dict[str, Any]) -> str:
    """Extract assistant text from an OpenAI-compatible response."""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible response has no choices")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenAI-compatible response has no message")

    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("OpenAI-compatible response has no text content")

    return content


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
