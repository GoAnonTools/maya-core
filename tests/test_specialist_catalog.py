import unittest

from app.workers.capabilities import WorkerCapability, WorkerRole
from app.workers.specialists.catalog import SpecialistCapabilityCatalog


class FutureSpecialistProfile:
    worker_id = "future-specialist"

    def capability_metadata(self):
        return WorkerCapability(
            worker_id=self.worker_id,
            role=WorkerRole.SPECIALIST,
            display_name="Future Specialist",
            capabilities=frozenset({"future_task"}),
            availability=False,
        )


class SpecialistCapabilityCatalogTests(unittest.TestCase):
    def test_catalog_supports_future_profiles(self):
        catalog = SpecialistCapabilityCatalog()
        catalog.register(FutureSpecialistProfile())

        self.assertEqual(
            [capability.worker_id for capability in catalog.list_capabilities()],
            ["coding-specialist", "future-specialist"],
        )
        self.assertFalse(catalog.is_executable("future-specialist"))

    def test_duplicate_profiles_are_rejected(self):
        catalog = SpecialistCapabilityCatalog()
        catalog.register(FutureSpecialistProfile())

        with self.assertRaises(ValueError):
            catalog.register(FutureSpecialistProfile())

    def test_non_specialist_profiles_are_rejected(self):
        class ConversationProfile:
            worker_id = "conversation"

            def capability_metadata(self):
                return WorkerCapability(
                    worker_id=self.worker_id,
                    role=WorkerRole.CONVERSATIONAL,
                    display_name="Conversation",
                )

        with self.assertRaises(ValueError):
            SpecialistCapabilityCatalog([ConversationProfile()])
