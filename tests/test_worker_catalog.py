import unittest

from app.workers.catalog import DEFAULT_WORKER_ID, create_worker_catalog
from app.workers.capabilities import WorkerRole
from app.workers.openai_compatible import OpenAICompatibleWorker
from app.workers.ministral import MinistralWorker


class WorkerCatalogTests(unittest.TestCase):
    def test_catalog_registers_existing_default_worker(self):
        registry = create_worker_catalog()

        self.assertEqual(
            registry.list_workers(),
            [DEFAULT_WORKER_ID, "ministral"],
        )
        self.assertIsInstance(
            registry.get(DEFAULT_WORKER_ID),
            OpenAICompatibleWorker,
        )

    def test_catalog_attaches_worker_capability_metadata(self):
        registry = create_worker_catalog()

        capability = registry.get_capability(DEFAULT_WORKER_ID)

        self.assertEqual(capability.worker_id, DEFAULT_WORKER_ID)
        self.assertEqual(capability.role, WorkerRole.CONVERSATIONAL)
        self.assertEqual(
            capability.display_name,
            "OpenAI-compatible worker",
        )
        self.assertEqual(
            capability.capabilities,
            frozenset({"chat", "streaming", "conversational"}),
        )
        self.assertTrue(capability.availability)

    def test_catalog_registers_specialist_and_offline_metadata_only(self):
        registry = create_worker_catalog()

        self.assertEqual(
            registry.list_workers(),
            [DEFAULT_WORKER_ID, "ministral"],
        )

        specialist = registry.get_capability("specialist")
        self.assertEqual(specialist.role, WorkerRole.SPECIALIST)
        self.assertFalse(specialist.availability)

        offline = registry.get_capability("offline-fallback")
        self.assertEqual(offline.role, WorkerRole.FALLBACK)
        self.assertFalse(offline.availability)

    def test_catalog_registers_ministral_worker_and_metadata(self):
        registry = create_worker_catalog()

        self.assertIsInstance(registry.get("ministral"), MinistralWorker)
        capability = registry.get_capability("ministral")
        self.assertEqual(capability.role, WorkerRole.CONVERSATIONAL)
        self.assertEqual(
            capability.capabilities,
            frozenset({"chat", "streaming", "conversational"}),
        )
