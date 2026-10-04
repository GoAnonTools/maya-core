import unittest

from app.workers.capabilities import WorkerRole
from app.workers.specialists.coding import CodingSpecialistProfile
from app.workers.specialists.catalog import SpecialistCapabilityCatalog


class CodingSpecialistProfileTests(unittest.TestCase):
    def test_declares_identity_and_role(self):
        profile = CodingSpecialistProfile()

        self.assertEqual(profile.worker_id, "coding-specialist")
        self.assertEqual(profile.role, WorkerRole.SPECIALIST)
        self.assertEqual(profile.description.startswith("Specialist"), True)

    def test_declares_coding_capabilities(self):
        profile = CodingSpecialistProfile()

        self.assertEqual(
            profile.capabilities,
            frozenset(
                {
                    "coding",
                    "repository_access",
                    "filesystem_read",
                    "filesystem_write",
                    "testing",
                }
            ),
        )

    def test_declares_permission_requirements_and_task_categories(self):
        profile = CodingSpecialistProfile()

        self.assertEqual(
            profile.required_permissions,
            frozenset({"filesystem_read", "filesystem_write", "execute"}),
        )
        self.assertEqual(
            profile.supported_task_categories,
            frozenset({"coding"}),
        )

    def test_capability_metadata_is_non_executable(self):
        metadata = CodingSpecialistProfile().capability_metadata()

        self.assertEqual(metadata.worker_id, "coding-specialist")
        self.assertFalse(metadata.availability)
        self.assertEqual(
            metadata.metadata["supported_task_categories"],
            ["coding"],
        )

    def test_catalog_contains_coding_profile_without_executable_worker(self):
        catalog = SpecialistCapabilityCatalog()

        capability = catalog.get("coding-specialist")

        self.assertEqual(capability.display_name, "Coding Specialist")
        self.assertFalse(catalog.is_executable("coding-specialist"))
        self.assertEqual(
            [profile.worker_id for profile in catalog.list_profiles()],
            ["coding-specialist"],
        )
