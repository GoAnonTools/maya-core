import os
from typing import Any

import yaml

from app.config import IDENTITY_CONFIG_PATH

DEFAULT_SYSTEM_PROMPT = "You are Maya."


def load_identity() -> dict[str, Any]:
    """Load Maya's identity configuration from the project config directory."""
    with IDENTITY_CONFIG_PATH.open("r", encoding="utf-8") as identity_file:
        identity = yaml.safe_load(identity_file)

    if not isinstance(identity, dict):
        raise ValueError("Maya identity configuration must contain a mapping")

    return identity


def render_system_prompt(context: dict[str, Any] | None = None) -> str:
    """Render the per-request context template for prompt injection.

    The template carries only request-scoped values ({user_name},
    {current_mode}); personality lives in Hermes's SOUL.md. Unknown
    placeholders are left blank rather than raising, so a template edit can
    never break the request path. ``str.format`` would raise KeyError on a
    stray ``{...}`` or on any literal brace in the template, hence the
    explicit mapping instead of ``format(**values)``.
    """
    request = context if isinstance(context, dict) else {}
    identity = load_identity()
    template = identity.get("system_prompt_template")

    if not isinstance(template, str) or not template.strip():
        return DEFAULT_SYSTEM_PROMPT

    values = {
        "user_name": os.getenv("MAYA_USER_NAME", "David"),
        "current_mode": request.get("mode") or os.getenv("MAYA_MODE", "online"),
    }
    for name, value in values.items():
        template = template.replace("{" + name + "}", str(value))

    return template.strip()
