import unittest

from app.orchestration import NormalizedRequest, Orchestrator
from app.routing import (
    BasicRoutingPolicy,
    RoutingContext,
    RoutingDecision,
)
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole


class StubWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok", "message": "executed"}

    def stream(self, context, route):
        yield "executed"


def build_registry(available=True):
    registry = WorkerRegistry()
    registry.register(
        "default",
        StubWorker(),
        WorkerCapability(
            worker_id="default",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Default worker",
            capabilities=frozenset({"chat", "streaming"}),
            availability=available,
        ),
    )
    return registry


class BasicRoutingPolicyTests(unittest.TestCase):
    def test_selects_default_registered_worker(self):
        request = NormalizedRequest(
            context={"message": "hello"},
            route={"model": "configured"},
            metadata={"source": "test"},
        )
        registry = build_registry()
        context = RoutingContext(
            request=request,
            worker_registry=registry,
            default_worker_id="default",
            required_capabilities=frozenset({"chat"}),
        )

        decision = BasicRoutingPolicy().decide(context)

        self.assertIsInstance(decision, RoutingDecision)
        self.assertEqual(decision.worker_id, "default")
        self.assertIn("matches required capabilities", decision.reason)
        self.assertEqual(
            decision.metadata["request_metadata"],
            {"source": "test"},
        )
        self.assertEqual(decision.metadata["matched_capabilities"], ["chat"])

    def test_rejects_missing_default_capability(self):
        request = NormalizedRequest(context={}, route={})
        context = RoutingContext(
            request=request,
            worker_registry=WorkerRegistry(),
            default_worker_id="default",
            required_capabilities=frozenset({"specialized_tasks"}),
        )

        with self.assertRaises(LookupError):
            BasicRoutingPolicy().decide(context)

    def test_rejects_unavailable_default_worker(self):
        request = NormalizedRequest(context={}, route={})
        registry = build_registry(available=False)
        context = RoutingContext(
            request=request,
            worker_registry=registry,
            default_worker_id="default",
        )

        with self.assertRaises(RuntimeError):
            BasicRoutingPolicy().decide(context)

    def test_rejects_required_capability_not_provided_by_default_worker(self):
        request = NormalizedRequest(context={}, route={})
        registry = build_registry()
        context = RoutingContext(
            request=request,
            worker_registry=registry,
            default_worker_id="default",
            required_capabilities=frozenset({"specialized_tasks"}),
        )

        with self.assertRaises(LookupError):
            BasicRoutingPolicy().decide(context)


class OrchestratorRoutingTests(unittest.TestCase):
    def test_orchestrator_executes_policy_selected_default_worker(self):
        registry = build_registry()
        orchestrator = Orchestrator(registry, default_worker_id="default")

        result = orchestrator.execute(
            NormalizedRequest(context={"message": "hello"}, route={})
        )

        self.assertEqual(result["message"], "executed")
