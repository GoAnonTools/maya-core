"""Capability-only catalog for specialist worker profiles."""

from collections.abc import Iterable
from typing import Protocol

from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.specialists.coding import CodingSpecialistProfile


class SpecialistCapabilityProfile(Protocol):
    """Shape required for a metadata-only specialist profile."""

    worker_id: str

    def capability_metadata(self) -> WorkerCapability:
        """Return capability metadata without creating an executable worker."""


class SpecialistCapabilityCatalog:
    """Store specialist capability profiles separately from worker instances."""

    def __init__(
        self,
        profiles: Iterable[SpecialistCapabilityProfile] | None = None,
    ) -> None:
        self._profiles: dict[str, SpecialistCapabilityProfile] = {}
        self._capabilities: dict[str, WorkerCapability] = {}

        initial_profiles = (
            profiles if profiles is not None else [CodingSpecialistProfile()]
        )
        for profile in initial_profiles:
            self.register(profile)

    def register(self, profile: SpecialistCapabilityProfile) -> None:
        """Register a specialist profile and its capability metadata."""
        capability = profile.capability_metadata()

        if capability.role != WorkerRole.SPECIALIST:
            raise ValueError("Specialist profile must have specialist role")

        if capability.worker_id != profile.worker_id:
            raise ValueError(
                "Profile worker_id must match capability worker_id"
            )

        if profile.worker_id in self._profiles:
            raise ValueError(
                f"Specialist profile already registered: {profile.worker_id}"
            )

        self._profiles[profile.worker_id] = profile
        self._capabilities[profile.worker_id] = capability

    def get(self, worker_id: str) -> WorkerCapability:
        """Return metadata for a registered specialist profile."""
        try:
            return self._capabilities[worker_id]
        except KeyError as exc:
            raise KeyError(f"Unknown specialist profile: {worker_id}") from exc

    def list_capabilities(self) -> list[WorkerCapability]:
        """Return specialist metadata in registration order."""
        return list(self._capabilities.values())

    def list_profiles(self) -> list[SpecialistCapabilityProfile]:
        """Return registered profiles in registration order."""
        return list(self._profiles.values())

    def is_executable(self, worker_id: str) -> bool:
        """Specialist profiles are metadata-only and never executable here."""
        if worker_id not in self._profiles:
            return False

        return False
