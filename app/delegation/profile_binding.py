"""Bind specialist capability metadata to delegation requests."""

from dataclasses import replace

from app.delegation.models import DelegationRequest
from app.workers.specialists.catalog import SpecialistCapabilityCatalog


def bind_specialist_profile(
    request: DelegationRequest,
    specialist_id: str,
    catalog: SpecialistCapabilityCatalog | None = None,
) -> DelegationRequest:
    """Return a request containing a snapshot of specialist metadata.

    This only enriches request metadata. It does not register, select, or
    execute a specialist worker.
    """
    profile_catalog = catalog or SpecialistCapabilityCatalog()
    capability = profile_catalog.get(specialist_id)

    return replace(
        request,
        specialist_id=capability.worker_id,
        specialist_role=capability.role,
        specialist_capabilities=capability.capabilities,
        specialist_metadata={
            "display_name": capability.display_name,
            "description": capability.description,
            "availability": capability.availability,
            **dict(capability.metadata),
        },
    )
