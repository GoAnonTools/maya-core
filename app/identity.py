from typing import Any

import yaml

from app.config import IDENTITY_CONFIG_PATH


def load_identity() -> dict[str, Any]:
    """Load Maya's identity configuration from the project config directory."""
    with IDENTITY_CONFIG_PATH.open("r", encoding="utf-8") as identity_file:
        identity = yaml.safe_load(identity_file)

    if not isinstance(identity, dict):
        raise ValueError("Maya identity configuration must contain a mapping")

    return identity
