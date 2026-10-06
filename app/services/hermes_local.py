"""Optional local Hermes executor construction."""

from pathlib import Path
from typing import Any

from app.services.hermes_config import HermesLocalConfig
from app.services.hermes_executor import HermesExecutor
from app.services.hermes_http_transport import HermesHttpTransport
from app.services.hermes_persistence import HermesRunPersistence
from app.services.hermes_transport import TransportHermesClient


def build_local_hermes_executor(
    http_client: Any,
    *,
    config: HermesLocalConfig | None = None,
    persistence: HermesRunPersistence | None = None,
    persistence_path: str | Path | None = None,
) -> HermesExecutor:
    """Build a local Hermes adapter only when explicitly enabled.

    The helper performs no work when disabled and never registers the
    executor with routing or a worker catalog.
    """
    local_config = config or HermesLocalConfig.from_environment()
    local_config.validate()
    if not local_config.enabled:
        return HermesExecutor(
            persistence=persistence,
            persistence_path=persistence_path,
            required_permissions=local_config.permissions,
        )

    transport = HermesHttpTransport(
        http_client,
        config=local_config.transport_config(),
    )
    return HermesExecutor(
        client=TransportHermesClient(transport),
        persistence=persistence,
        persistence_path=persistence_path,
        required_permissions=local_config.permissions,
    )
