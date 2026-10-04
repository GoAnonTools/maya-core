import unittest

from app.orchestration import NormalizedRequest, Orchestrator
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole


class StubWorker(Worker):
    def __init__(self, result):
        self.result = result
        self.execute_calls = []
        self.stream_calls = []

    def execute(self, context, route):
        self.execute_calls.append((context, route))
        return self.result

    def stream(self, context, route):
        self.stream_calls.append((context, route))
        yield "Hello"
        yield " Maya"


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.registry = WorkerRegistry()
        self.worker = StubWorker({"status": "ok", "message": "Hello"})
        self.registry.register(
            "default",
            self.worker,
            WorkerCapability(
                worker_id="default",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Default worker",
            ),
        )
        self.orchestrator = Orchestrator(
            self.registry,
            default_worker_id="default",
        )
        self.request = NormalizedRequest(
            context={"message": "Hello Maya"},
            route={"model": "configured-model"},
        )

    def test_execute_uses_configured_default_worker(self):
        result = self.orchestrator.execute(self.request)

        self.assertEqual(result, {"status": "ok", "message": "Hello"})
        self.assertEqual(
            self.worker.execute_calls,
            [(self.request.context, self.request.route)],
        )

    def test_stream_uses_configured_default_worker(self):
        chunks = list(self.orchestrator.stream(self.request))

        self.assertEqual(chunks, ["Hello", " Maya"])
        self.assertEqual(
            self.worker.stream_calls,
            [(self.request.context, self.request.route)],
        )

    def test_missing_default_worker_is_reported_by_registry(self):
        orchestrator = Orchestrator(self.registry, default_worker_id="missing")

        with self.assertRaises(LookupError):
            orchestrator.execute(self.request)
