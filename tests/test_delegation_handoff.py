import unittest

from app.delegation import DelegationRequest
from app.orchestration import NormalizedRequest, Orchestrator
from app.routing import RoutingFailure
from app.workers import Worker, WorkerCapability, WorkerRegistry, WorkerRole


class StubWorker(Worker):
    def execute(self, context, route):
        return {"status": "ok", "message": "conversation response"}

    def stream(self, context, route):
        yield "conversation response"


def build_registry(*, specialist_available=True):
    registry = WorkerRegistry()
    registry.register(
        "default",
        StubWorker(),
        WorkerCapability(
            worker_id="default",
            role=WorkerRole.CONVERSATIONAL,
            display_name="Default worker",
            capabilities=frozenset({"conversation", "conversational", "chat"}),
        ),
    )
    registry.register_capability(
        WorkerCapability(
            worker_id="specialist",
            role=WorkerRole.SPECIALIST,
            display_name="Specialist worker",
            capabilities=frozenset({"coding", "research"}),
            availability=specialist_available,
            metadata={"worker_type": "specialist"},
        )
    )
    return registry


class DelegationHandoffTests(unittest.TestCase):
    def test_conversation_remains_on_normal_worker_path(self):
        orchestrator = Orchestrator(
            build_registry(),
            default_worker_id="default",
        )

        result = orchestrator.execute(
            NormalizedRequest(
                context={"message": "Hello"},
                route={},
                request_id="request-conversation",
            )
        )

        self.assertEqual(result["status"], "ok")

    def test_specialist_request_creates_delegation_request_only(self):
        orchestrator = Orchestrator(
            build_registry(),
            default_worker_id="default",
        )

        delegation = orchestrator.prepare_delegation_request(
            NormalizedRequest(
                context={"message": "Review this code"},
                route={},
                metadata={"required_capabilities": ["coding"]},
                request_id="request-specialist",
                session_id="session-1",
            )
        )

        self.assertIsInstance(delegation, DelegationRequest)
        self.assertEqual(delegation.task, "Review this code")
        self.assertEqual(delegation.request_id, "request-specialist")
        self.assertEqual(delegation.session_id, "session-1")
        self.assertEqual(delegation.required_capabilities, frozenset({"coding"}))
        self.assertEqual(
            delegation.selected_worker["worker_id"],
            "specialist",
        )
        self.assertEqual(
            delegation.selected_worker["role"],
            "specialist",
        )

    def test_unavailable_specialist_fails_explainably(self):
        orchestrator = Orchestrator(
            build_registry(specialist_available=False),
            default_worker_id="default",
        )

        with self.assertRaises(RoutingFailure) as raised:
            orchestrator.prepare_delegation_request(
                NormalizedRequest(
                    context={"message": "Review this code"},
                    route={},
                    metadata={"required_capabilities": ["coding"]},
                )
            )

        self.assertEqual(
            raised.exception.reason_code,
            "specialist_unavailable",
        )
        self.assertEqual(raised.exception.worker_id, "specialist")
