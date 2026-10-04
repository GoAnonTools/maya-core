import unittest

from app.orchestration import NormalizedRequest, Orchestrator
from app.routing import RoutingContext, BasicRoutingPolicy
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole


class StubWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok", "message": "done"}

    def stream(self, context, route):
        yield "done"


def build_registry(ministral_available=True):
    registry = WorkerRegistry()
    registry.register(
        "default",
        StubWorker(),
        WorkerCapability(
            worker_id="default",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Default",
            capabilities=frozenset({"conversational", "chat"}),
            metadata={"fallback_for": ["conversational"]},
        ),
    )
    registry.register(
        "ministral",
        StubWorker(),
        WorkerCapability(
            worker_id="ministral",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Ministral",
            capabilities=frozenset({"conversational", "chat"}),
            availability=ministral_available,
            metadata={"preferred_for": ["conversational"]},
        ),
    )
    return registry


class RoutingObservabilityTests(unittest.TestCase):
    def test_logs_preferred_worker_decision(self):
        orchestrator = Orchestrator(
            build_registry(),
            default_worker_id="default",
        )
        request = NormalizedRequest(
            context={},
            route={},
            request_id="request-preferred",
        )

        with self.assertLogs("maya.routing", level="INFO") as captured:
            orchestrator.execute(request)

        record = captured.records[0]
        self.assertEqual(
            record.routing_decision,
            {
                "request_id": "request-preferred",
                "required_capabilities": ["conversational"],
                "selected_worker_id": "ministral",
                "selected_role": "conversational",
                "reason_code": "conversation_preferred",
                "fallback_used": False,
            },
        )

    def test_logs_fallback_usage(self):
        orchestrator = Orchestrator(
            build_registry(ministral_available=False),
            default_worker_id="default",
        )
        request = NormalizedRequest(
            context={},
            route={},
            metadata={"request_id": "request-fallback"},
        )

        with self.assertLogs("maya.routing", level="INFO") as captured:
            orchestrator.execute(request)

        decision = captured.records[0].routing_decision
        self.assertEqual(decision["request_id"], "request-fallback")
        self.assertEqual(decision["selected_worker_id"], "default")
        self.assertEqual(decision["reason_code"], "default_fallback")
        self.assertTrue(decision["fallback_used"])
