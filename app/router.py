from typing import Any

from app.settings import load_settings


def select_model(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Select the model target for the configured Maya mode.

    This function only returns routing metadata. It does not connect to or call
    the selected model endpoint.
    """
    current_settings = settings if settings is not None else load_settings()
    maya = _as_mapping(current_settings.get("maya"))
    services = _as_mapping(current_settings.get("services"))
    model_service = _as_mapping(services.get("model"))
    mode = maya.get("mode")

    if mode == "online":
        return {
            "mode": mode,
            "model": model_service.get(
                "model",
                "NousResearch/Hermes-3-Llama-3.1-8B",
            ),
            "provider": model_service.get("provider", "lightning"),
            "base_url": model_service.get("base_url"),
            "endpoint": model_service.get("endpoint"),
        }

    if mode == "offline":
        return {
            "mode": mode,
            "model": "qwen_local",
            "provider": "local",
            "base_url": None,
            "endpoint": None,
        }

    raise ValueError(f"Unsupported Maya mode: {mode!r}")


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
