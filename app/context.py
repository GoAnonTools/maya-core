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
        results = []

        for query in _memory_queries(normalized_message):
            results.extend(search_memory(query))

        seen = set()

        memories = [
            item.get("content")
            for item in results
            if isinstance(item.get("content"), str)
            and not (
                item.get("content") in seen
                or seen.add(item.get("content"))
            )
        ][:5]

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


def _memory_queries(message: str) -> list[str]:
    words = [
        word.strip(".,?!:;")
        for word in message.split()
    ]

    ignored = {
        "the",
        "a",
        "an",
        "what",
        "which",
        "do",
        "i",
        "you",
        "my",
        "me",
        "is",
        "are",
        "to",
        "of",
        "and",
        "kind",
    }

    return [
        word
        for word in words
        if len(word) >= 3
        and word.lower() not in ignored
    ]


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
