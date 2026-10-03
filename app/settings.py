from typing import Any

import yaml

from app.config import MAYA_CONFIG_PATH


def load_settings() -> dict[str, Any]:
    """Load Maya Core settings from the local YAML configuration file."""
    with MAYA_CONFIG_PATH.open("r", encoding="utf-8") as settings_file:
        settings = yaml.safe_load(settings_file)

    if not isinstance(settings, dict):
        raise ValueError("Maya configuration must contain a mapping")

    return settings


def get_public_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return only non-sensitive settings suitable for the status endpoint."""
    maya = _as_mapping(settings.get("maya"))
    services = _as_mapping(settings.get("services"))
    model = _as_mapping(services.get("model"))
    memory = _as_mapping(services.get("memory"))
    agent_os = _as_mapping(services.get("agent_os"))

    return {
        "maya": {
            "mode": maya.get("mode"),
        },
        "services": {
            "model": {
                "provider": model.get("provider"),
                "endpoint": model.get("endpoint"),
            },
            "memory": {
                "provider": memory.get("provider"),
                "endpoint": memory.get("endpoint"),
            },
            "agent_os": {
                "enabled": agent_os.get("enabled", False),
                "endpoint": agent_os.get("endpoint"),
            },
        },
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
