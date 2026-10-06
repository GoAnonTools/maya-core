"""Explicit local Hermes endpoint configuration."""

from dataclasses import dataclass
import os
from urllib.parse import urlparse

from app.services.hermes_http_transport import HermesHttpTransportConfig


@dataclass(frozen=True)
class HermesLocalConfig:
    """Validated, opt-in configuration for a local Hermes service."""

    enabled: bool = False
    endpoint: str = ""
    auth_token: str | None = None
    permissions: frozenset[str] = frozenset()
    submission_timeout: float = 10.0
    stream_timeout: float = 30.0
    cancellation_timeout: float = 10.0
    max_reconnects: int = 2

    @classmethod
    def from_environment(cls) -> "HermesLocalConfig":
        return cls(
            enabled=os.getenv("MAYA_HERMES_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            endpoint=os.getenv("MAYA_HERMES_ENDPOINT", ""),
            auth_token=os.getenv("MAYA_HERMES_AUTH_TOKEN"),
            permissions=_csv_environment("MAYA_HERMES_PERMISSIONS"),
            submission_timeout=float(
                os.getenv("MAYA_HERMES_SUBMISSION_TIMEOUT", "10")
            ),
            stream_timeout=float(
                os.getenv("MAYA_HERMES_STREAM_TIMEOUT", "30")
            ),
            cancellation_timeout=float(
                os.getenv("MAYA_HERMES_CANCELLATION_TIMEOUT", "10")
            ),
            max_reconnects=int(os.getenv("MAYA_HERMES_MAX_RECONNECTS", "2")),
        )

    def validate(self) -> "HermesLocalConfig":
        """Validate configuration without contacting Hermes."""
        if not self.enabled:
            return self
        if not self.endpoint.strip():
            raise ValueError(
                "MAYA_HERMES_ENDPOINT is required when Hermes is enabled"
            )

        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "Hermes endpoint must be an absolute http(s) URL"
            )
        if (
            self.submission_timeout <= 0
            or self.stream_timeout <= 0
            or self.cancellation_timeout <= 0
        ):
            raise ValueError("Hermes timeouts must be greater than zero")
        if self.max_reconnects < 0:
            raise ValueError("Hermes max_reconnects must not be negative")
        return self

    def transport_config(self) -> HermesHttpTransportConfig:
        """Convert validated local settings to HTTP transport settings."""
        self.validate()
        return HermesHttpTransportConfig(
            endpoint=self.endpoint,
            auth_token=self.auth_token,
            submission_timeout=self.submission_timeout,
            stream_timeout=self.stream_timeout,
            cancellation_timeout=self.cancellation_timeout,
            max_reconnects=self.max_reconnects,
        )


def _csv_environment(name: str) -> frozenset[str]:
    return frozenset(
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    )
