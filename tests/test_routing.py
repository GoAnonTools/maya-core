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
            capabilities=frozenset({"chat", "streaming", "conversational"}),
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
        self.assertEqual(
            decision.metadata["matched_capabilities"],
            ["chat"],
        )

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

    def test_conversational_capability_selects_preferred_worker(self):
        registry = WorkerRegistry()
        registry.register(
            "default",
            StubWorker(),
            WorkerCapability(
                worker_id="default",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Default worker",
                capabilities=frozenset({"chat", "streaming", "conversational"}),
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
                capabilities=frozenset({"chat", "streaming", "conversational"}),
                metadata={"preferred_for": ["conversational"]},
            ),
        )
        context = RoutingContext(
            request=NormalizedRequest(context={}, route={}),
            worker_registry=registry,
            default_worker_id="default",
            required_capabilities=frozenset({"conversational"}),
        )

        decision = BasicRoutingPolicy().decide(context)

        self.assertEqual(decision.worker_id, "ministral")
        self.assertIn("preferred conversational", decision.reason)

    def test_unavailable_ministral_falls_back_to_default_worker(self):
        registry = build_registry()
        registry.register(
            "ministral",
            StubWorker(),
            WorkerCapability(
                worker_id="ministral",
                role=WorkerRole.CONVERSATIONAL,
                display_name="Ministral",
                capabilities=frozenset({"chat", "streaming", "conversational"}),
                availability=False,
                metadata={"preferred_for": ["conversational"]},
            ),
        )
        context = RoutingContext(
            request=NormalizedRequest(context={}, route={}),
            worker_registry=registry,
            default_worker_id="default",
            required_capabilities=frozenset({"conversational"}),
        )

        decision = BasicRoutingPolicy().decide(context)

        self.assertEqual(decision.worker_id, "default")
        self.assertIn("fallback", decision.reason)

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
