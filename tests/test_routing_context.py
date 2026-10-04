import unittest

from app.orchestration import NormalizedRequest, Orchestrator
from app.routing import TaskCategory, TaskClassification
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole


class StubWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok"}

    def stream(self, context, route):
        yield "ok"


class RoutingContextClassificationTests(unittest.TestCase):
    def test_orchestrator_prepares_classification_without_changing_execution(self):
        registry = WorkerRegistry()
        registry.register(
            "default",
            StubWorker(),
            WorkerCapability(
                worker_id="default",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Default",
                capabilities=frozenset({"conversational"}),
            ),
        )
        captured = {}

        class CapturingPolicy:
            def decide(self, context):
                captured["classification"] = context.classification
                captured["task_capabilities"] = context.task_capabilities
                return type(
                    "Decision",
                    (),
                    {
                        "worker_id": "default",
                        "capability": registry.get_capability("default"),
                        "reason_code": "test",
                        "fallback_used": False,
                        "metadata": {},
                    },
                )()

        result = Orchestrator(
            registry,
            default_worker_id="default",
            routing_policy=CapturingPolicy(),
        ).execute(NormalizedRequest(context={}, route={}))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            captured["classification"].category,
            TaskCategory.CONVERSATION,
        )
        self.assertEqual(
            captured["task_capabilities"],
            frozenset({"conversation"}),
        )
