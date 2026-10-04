import unittest

from app.workers import Worker, WorkerRegistry


class StubWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok"}

    def stream(self, context, route):
        yield "chunk"


class AvailableWorker(StubWorker):
    def __init__(self, available):
        self.available = available

    def is_available(self):
        return self.available


class WorkerRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = WorkerRegistry()
        self.worker = StubWorker()

    def test_register_and_retrieve_worker(self):
        self.registry.register("conversation", self.worker)

        self.assertIs(self.registry.get("conversation"), self.worker)

    def test_register_and_retrieve_capability(self):
        from app.workers.capabilities import WorkerCapability, WorkerRole

        capability = WorkerCapability(
            worker_id="conversation",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Conversation",
        )

        self.registry.register(
            "conversation",
            self.worker,
            capability=capability,
        )

        self.assertIs(
            self.registry.get_capability("conversation"),
            capability,
        )

    def test_register_capability_without_worker(self):
        from app.workers.capabilities import WorkerCapability, WorkerRole

        capability = WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Specialist",
        )

        self.registry.register_capability(capability)

        self.assertEqual(self.registry.list_workers(), [])
        self.assertIs(
            self.registry.get_capability("specialist"),
            capability,
        )
        self.assertFalse(self.registry.is_available("specialist"))

    def test_list_workers_returns_registered_ids(self):
        self.registry.register("first", StubWorker())
        self.registry.register("second", StubWorker())

        self.assertEqual(self.registry.list_workers(), ["first", "second"])

    def test_availability_is_false_for_unknown_worker(self):
        self.assertFalse(self.registry.is_available("missing"))

    def test_registered_worker_without_availability_hook_is_available(self):
        self.registry.register("conversation", self.worker)

        self.assertTrue(self.registry.is_available("conversation"))

    def test_optional_availability_hook_is_respected(self):
        self.registry.register("ready", AvailableWorker(True))
        self.registry.register("unready", AvailableWorker(False))

        self.assertTrue(self.registry.is_available("ready"))
        self.assertFalse(self.registry.is_available("unready"))

    def test_duplicate_worker_id_is_rejected(self):
        self.registry.register("conversation", self.worker)

        with self.assertRaises(ValueError):
            self.registry.register("conversation", StubWorker())

    def test_invalid_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register("", self.worker)

        with self.assertRaises(TypeError):
            self.registry.register("not-a-worker", object())

    def test_capability_id_must_match_worker_id(self):
        from app.workers.capabilities import WorkerCapability, WorkerRole

        capability = WorkerCapability(
            worker_id="different",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Conversation",
        )

        with self.assertRaises(ValueError):
            self.registry.register(
                "conversation",
                self.worker,
                capability=capability,
            )

    def test_unknown_worker_lookup_is_rejected(self):
        with self.assertRaises(KeyError):
            self.registry.get("missing")
