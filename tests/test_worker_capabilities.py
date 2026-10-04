import unittest

from app.workers.capabilities import WorkerCapability, WorkerRole


class WorkerCapabilityTests(unittest.TestCase):
    def test_roles_have_stable_serializable_values(self):
        self.assertEqual(WorkerRole.CONVERSATIONAL.value, "conversational")
        self.assertEqual(WorkerRole.SPECIALIST.value, "specialist")
        self.assertEqual(WorkerRole.FALLBACK.value, "fallback")

    def test_capability_defaults(self):
        capability = WorkerCapability(
            worker_id="conversation",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Conversation worker",
        )

        self.assertEqual(capability.worker_id, "conversation")
        self.assertEqual(capability.role, WorkerRole.CONVERSATIONAL)
        self.assertEqual(capability.display_name, "Conversation worker")
        self.assertEqual(capability.capabilities, frozenset())
        self.assertTrue(capability.availability)
        self.assertIsNone(capability.description)
        self.assertIsNone(capability.priority)
        self.assertEqual(capability.metadata, {})

    def test_capability_stores_descriptive_metadata(self):
        capability = WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Specialist worker",
            capabilities=frozenset({"streaming", "tools"}),
            availability=False,
            description="Handles specialized tasks.",
            priority=20,
            metadata={"scope": "task-specific"},
        )

        self.assertEqual(
            capability.capabilities,
            frozenset({"streaming", "tools"}),
        )
        self.assertFalse(capability.availability)
        self.assertEqual(capability.description, "Handles specialized tasks.")
        self.assertEqual(capability.priority, 20)
        self.assertEqual(capability.metadata, {"scope": "task-specific"})

    def test_metadata_defaults_are_not_shared(self):
        first = WorkerCapability("one", WorkerRole.FALLBACK, "One")
        second = WorkerCapability("two", WorkerRole.FALLBACK, "Two")

        first.metadata["key"] = "value"

        self.assertEqual(second.metadata, {})
