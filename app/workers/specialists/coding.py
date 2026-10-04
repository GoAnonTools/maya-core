"""Capability profile for the Coding Specialist."""

from dataclasses import dataclass, field

from app.workers.capabilities import WorkerCapability, WorkerRole


@dataclass(frozen=True)
class CodingSpecialistProfile:
    """Declarative metadata for a future Coding Specialist worker."""

    worker_id: str = "coding-specialist"
    role: WorkerRole = WorkerRole.SPECIALIST
    capabilities: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "coding",
                "repository_access",
                "filesystem_read",
                "filesystem_write",
                "testing",
            }
        )
    )
    required_permissions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "filesystem_read",
                "filesystem_write",
                "execute",
            }
        )
    )
    description: str = (
        "Specialist for repository analysis, code changes, testing, "
        "and documentation work."
    )
    supported_task_categories: frozenset[str] = field(
        default_factory=lambda: frozenset({"coding"})
    )

    def capability_metadata(self) -> WorkerCapability:
        """Return generic worker capability metadata without registering it."""
        return WorkerCapability(
            worker_id=self.worker_id,
            role=self.role,
            display_name="Coding Specialist",
            capabilities=self.capabilities,
            availability=False,
            description=self.description,
            metadata={
                "required_permissions": sorted(self.required_permissions),
                "supported_task_categories": sorted(
                    self.supported_task_categories
                ),
            },
        )
