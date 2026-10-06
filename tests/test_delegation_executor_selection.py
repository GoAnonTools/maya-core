import unittest

from app.delegation import (
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
    OptInHermesExecutorSelector,
)
from app.delegation.policy import HermesDelegationPolicy
from app.services.lightning_executor import (
    ExecutorCapabilities,
    InMemoryLightningExecutor,
    LightningExecutor,
    LightningSession,
)
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


class FakeExecutor(LightningExecutor):
    def __init__(self, backend, categories):
        self.backend = backend
        self.categories = frozenset(categories)
        self.jobs = {}
        self.cancelled = []
        self.manager = None

    @property
    def backend_name(self):
        return self.backend

    def is_available(self):
        return True

    def capabilities(self):
        return ExecutorCapabilities(
            supported_task_categories=self.categories,
            available=True,
            version="fake-1",
            metadata={"backend": self.backend},
        )

    def submit(self, job: LightningJob):
        execution_id = f"{self.backend}-{job.delegation_id}"
        self.jobs[execution_id] = job
        return execution_id

    def stream_events(self, execution_id):
        job = self.get_session(execution_id).job
        yield LightningEvent(
            delegation_id=job.delegation_id,
            event_type=LightningEventType.STARTED,
        )
        if self.manager is not None:
            self.manager.cancel(job.delegation_id)
            yield LightningEvent(
                delegation_id=job.delegation_id,
                event_type=LightningEventType.CANCELLED,
            )
            return
        yield LightningEvent(
            delegation_id=job.delegation_id,
            event_type=LightningEventType.COMPLETED,
            result={"backend": self.backend},
        )

    def cancel(self, execution_id):
        self.cancelled.append(execution_id)

    def active_jobs(self):
        return 0

    def get_session(self, execution_id):
        return LightningSession(
            execution_id=execution_id,
            session_id="session",
            job=self.jobs[execution_id],
        )


class ExecutorSelectionTests(unittest.TestCase):
    def request(self, delegation_id="delegation-executor", **metadata):
        return DelegationRequest(
            delegation_id=delegation_id,
            task="Implement a coding change",
            metadata={"task_category": "coding", **metadata},
        )

    def setUp(self):
        self.hermes = FakeExecutor("hermes", {"coding"})
        self.fallback = InMemoryLightningExecutor()

    def selector(self, enabled=True):
        return OptInHermesExecutorSelector(
            hermes_executor=self.hermes,
            fallback_executor=self.fallback,
            policy=HermesDelegationPolicy(enabled=enabled),
        )

    def test_hermes_disabled_uses_inmemory_fallback(self):
        manager = DelegationManager()

        events = manager.execute_with_executor(
            self.request(),
            selector=self.selector(enabled=False),
        )

        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertEqual(events[1].metadata["execution_trace"]["target"], "in_memory")
        self.assertEqual(self.hermes.jobs, {})

    def test_hermes_enabled_uses_fake_hermes_executor(self):
        manager = DelegationManager()

        events = manager.execute_with_executor(
            self.request(),
            selector=self.selector(enabled=True),
        )

        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertEqual(events[1].metadata["execution_trace"]["target"], "hermes")
        self.assertEqual(list(self.hermes.jobs), ["hermes-delegation-executor"])

    def test_approval_required_blocks_submission(self):
        manager = DelegationManager()

        events = manager.execute_with_executor(
            self.request(requires_approval=True),
            selector=self.selector(enabled=True),
        )

        self.assertEqual(events[-1].status, DelegationStatus.WAITING_APPROVAL)
        self.assertEqual(manager.get_pending_approval("delegation-executor").approval_id, "approval-delegation-executor")
        self.assertEqual(self.hermes.jobs, {})

    def test_approved_task_can_resume_through_explicit_executor_flow(self):
        manager = DelegationManager()
        request = self.request(
            delegation_id="delegation-approved",
            requires_approval=True,
            approval_id="approval-approved",
        )
        manager.execute_with_executor(
            request,
            selector=self.selector(enabled=True),
        )
        manager.approve("delegation-approved", "approval-approved")

        events = manager.execute_with_executor(
            request,
            selector=self.selector(enabled=True),
        )

        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertEqual(
            events[-1].metadata["execution_trace"]["target"],
            "hermes",
        )

    def test_unsupported_capability_uses_fallback(self):
        manager = DelegationManager()
        request = self.request(
            delegation_id="delegation-research",
            task_category="research",
        )
        request = DelegationRequest(
            delegation_id=request.delegation_id,
            task="Research the topic",
            metadata=request.metadata,
        )

        events = manager.execute_with_executor(
            request,
            selector=self.selector(enabled=True),
        )

        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertEqual(events[1].metadata["execution_trace"]["target"], "in_memory")
        self.assertEqual(self.hermes.jobs, {})

    def test_cancellation_propagates_to_selected_executor(self):
        manager = DelegationManager()
        self.hermes.manager = manager

        events = manager.execute_with_executor(
            self.request(delegation_id="delegation-cancel"),
            selector=self.selector(enabled=True),
        )

        self.assertEqual(events[-1].status, DelegationStatus.CANCELLED)
        self.assertEqual(self.hermes.cancelled, ["hermes-delegation-cancel"])


if __name__ == "__main__":
    unittest.main()
