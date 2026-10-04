from typing import Any

from app.identity import load_identity
from app.settings import load_settings
from app.memory_client import search_memory


def create_request_context(message: str) -> dict[str, Any]:
    """Create the stable request package that will later be sent to Hermes."""
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("Message must not be empty")

    identity_config = load_identity()
    identity = _as_mapping(identity_config.get("identity"))
    maya = _as_mapping(load_settings().get("maya"))

    memories = []

    try:
        results = search_memory(normalized_message)
        memories = [
            item.get("content")
            for item in results[:5]
            if isinstance(item.get("content"), str)
        ]
    except Exception:
        memories = []

    context = {
        "maya": {
            "identity": identity.get("name", "Maya"),
        },
        "mode": maya.get("mode"),
        "message": normalized_message,
    }

    if memories:
        context["memory"] = memories

    system_prompt = identity_config.get("system_prompt_template")
    if isinstance(system_prompt, str) and system_prompt.strip():
        context["maya"]["system_prompt"] = system_prompt.strip()

    return context


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
