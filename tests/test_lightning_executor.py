import unittest
from collections.abc import Iterator
from tempfile import TemporaryDirectory

from app.services.hermes_client import HermesClient
from app.services.lightning import LightningService
from app.services.lightning_app import create_app
from app.services.lightning_executor import (
    ExecutorCapabilities,
    InMemoryLightningExecutor,
    LightningExecutor,
)
from app.services.hermes_executor import HermesExecutor
from app.services.hermes_protocol import (
    HermesEvent,
    HermesEventType,
    HermesJob,
)
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


class FakeLightningExecutor(LightningExecutor):
    """Controllable executor used to verify service dependency injection."""

    backend_name = "fake"

    def __init__(self):
        self.jobs = {}
        self.cancelled = set()

    def is_available(self) -> bool:
        return True

    def submit(self, job: LightningJob) -> str:
        execution_id = f"fake-{job.delegation_id}"
        self.jobs[execution_id] = job
        return execution_id

    def stream_events(self, execution_id: str):
        job = self.get_session(execution_id)
        yield LightningEvent(
            delegation_id=job.delegation_id,
            event_type=LightningEventType.STARTED,
        )
        if execution_id in self.cancelled:
            yield LightningEvent(
                delegation_id=job.delegation_id,
                event_type=LightningEventType.CANCELLED,
            )
            return
        yield LightningEvent(
            delegation_id=job.delegation_id,
            event_type=LightningEventType.COMPLETED,
        )

    def cancel(self, execution_id: str) -> None:
        self.get_session(execution_id)
        self.cancelled.add(execution_id)

    def active_jobs(self) -> int:
        return 0

    def get_session(self, execution_id: str) -> LightningJob:
        try:
            return self.jobs[execution_id]
        except KeyError as exc:
            raise KeyError(execution_id) from exc


class FakeHermesClient(HermesClient):
    """Scripted Hermes client with no network or process dependencies."""

    def __init__(self, events: list[HermesEvent] | None = None):
        self.jobs: list[HermesJob] = []
        self.cancelled: list[str] = []
        self.events = events or []

    def submit(self, job: HermesJob) -> str:
        self.jobs.append(job)
        return "hermes-run-1"

    def stream_events(self, run_id: str) -> Iterator[HermesEvent]:
        self.last_run_id = run_id
        yield from self.events

    def cancel(self, run_id: str) -> None:
        self.cancelled.append(run_id)

    def health(self):
        return {"status": "healthy", "available": True}


class LightningExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = FakeLightningExecutor()
        self.service = LightningService(executor=self.executor)
        self.job = LightningJob(
            delegation_id="fake-delegation",
            request_id=None,
            session_id=None,
            workspace="test-workspace",
        )

    def test_service_uses_injected_executor(self):
        execution_id = self.service.submit(self.job)

        self.assertEqual(execution_id, "fake-fake-delegation")
        self.assertIs(self.service.executor, self.executor)
        self.assertEqual(self.service.health()["backend"], "fake")

    def test_inmemory_executor_exposes_default_capabilities(self):
        capabilities = InMemoryLightningExecutor().capabilities()

        self.assertIsInstance(capabilities, ExecutorCapabilities)
        self.assertTrue(capabilities.available)
        self.assertEqual(capabilities.supported_task_categories, {"general"})
        self.assertEqual(capabilities.required_permissions, frozenset())
        self.assertEqual(capabilities.version, "1")

    def test_fake_executor_capabilities_are_available_without_routing(self):
        capabilities = self.executor.capabilities()

        self.assertTrue(capabilities.available)
        self.assertEqual(capabilities.metadata["backend"], "fake")

    def test_service_exposes_executor_capabilities(self):
        self.assertEqual(
            self.service.capabilities().metadata["backend"],
            "fake",
        )

    def test_injected_executor_emits_events_and_supports_cancellation(self):
        execution_id = self.service.submit(self.job)
        self.service.cancel(execution_id)

        self.assertEqual(
            [
                event.event_type
                for event in self.service.stream_events(execution_id)
            ],
            [LightningEventType.STARTED, LightningEventType.CANCELLED],
        )

    def test_fastapi_boundary_accepts_executor_injection(self):
        application = create_app(executor=self.executor)

        self.assertIs(
            application.state.lightning_service.executor,
            self.executor,
        )

    def test_hermes_executor_is_lightning_compatible_but_unavailable(self):
        executor = HermesExecutor()

        self.assertIsInstance(executor, LightningExecutor)
        self.assertFalse(executor.is_available())
        self.assertEqual(executor.metadata["status"], "disabled")
        self.assertFalse(executor.metadata["external_process"])
        self.assertFalse(executor.metadata["model_execution"])

    def test_unavailable_hermes_exposes_capabilities_without_a_client(self):
        capabilities = HermesExecutor().capabilities()

        self.assertFalse(capabilities.available)
        self.assertEqual(
            capabilities.supported_task_categories,
            {"coding", "research"},
        )
        self.assertEqual(capabilities.metadata["status"], "disabled")
        self.assertEqual(capabilities.version, "1")

    def test_hermes_executor_requires_injected_client(self):
        executor = HermesExecutor()

        with self.assertRaisesRegex(RuntimeError, "client is not configured"):
            executor.submit(self.job)

    def test_hermes_executor_maps_job_run_and_events(self):
        client = FakeHermesClient(
            [
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.STARTED,
                    message="Hermes started",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.PROGRESS,
                    progress=0.5,
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.COMPLETED,
                    result={"answer": "done"},
                ),
            ]
        )
        job = LightningJob(
            delegation_id="delegation-hermes",
            request_id="request-hermes",
            session_id="session-hermes",
            workspace="workspace",
            capabilities=frozenset({"coding"}),
            permissions=frozenset({"filesystem_read"}),
            metadata={"task": "Inspect the repository"},
        )
        executor = HermesExecutor(client=client)

        execution_id = executor.submit(job)
        events = list(executor.stream_events(execution_id))

        self.assertEqual(client.jobs[0].task, "Inspect the repository")
        self.assertEqual(executor.run_mapping(execution_id).run_id, "hermes-run-1")
        self.assertEqual(
            [event.event_type for event in events],
            [
                LightningEventType.STARTED,
                LightningEventType.PROGRESS,
                LightningEventType.COMPLETED,
            ],
        )
        self.assertEqual(events[-1].result, {"answer": "done"})
        self.assertEqual(client.last_run_id, "hermes-run-1")

    def test_hermes_executor_forwards_cancel_to_client(self):
        client = FakeHermesClient()
        executor = HermesExecutor(client=client)
        execution_id = executor.submit(self.job)

        executor.cancel(execution_id)

        self.assertEqual(client.cancelled, ["hermes-run-1"])

    def test_hermes_executor_replays_full_realistic_lifecycle(self):
        client = FakeHermesClient(
            [
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.RUN_STARTED,
                    message="Run started",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.MESSAGE_DELTA,
                    delta="Inspecting files",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.TOOL_STARTED,
                    tool_name="file_reader",
                    tool_call_id="tool-1",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.TOOL_COMPLETED,
                    tool_name="file_reader",
                    tool_call_id="tool-1",
                    result={"files": 3},
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.APPROVAL_REQUEST,
                    approval_id="approval-1",
                    message="Approval required",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.RUN_COMPLETED,
                    result={"answer": "finished"},
                ),
            ]
        )
        executor = HermesExecutor(client=client)
        execution_id = executor.submit(self.job)

        events = list(executor.stream_events(execution_id))

        self.assertEqual(
            [event.event_type for event in events],
            [
                LightningEventType.STARTED,
                LightningEventType.PROGRESS,
                LightningEventType.PROGRESS,
                LightningEventType.PROGRESS,
                LightningEventType.PROGRESS,
                LightningEventType.COMPLETED,
            ],
        )
        self.assertEqual(events[1].message, "Inspecting files")
        self.assertEqual(events[2].metadata["tool_name"], "file_reader")
        self.assertEqual(events[3].result, {"files": 3})
        self.assertTrue(events[4].metadata["approval_required"])
        self.assertEqual(events[4].metadata["approval_id"], "approval-1")
        self.assertEqual(events[5].result, {"answer": "finished"})

    def test_hermes_executor_maps_failed_and_cancelled_runs(self):
        for event_type, expected_type in (
            (HermesEventType.RUN_FAILED, LightningEventType.FAILED),
            (HermesEventType.RUN_CANCELLED, LightningEventType.CANCELLED),
        ):
            with self.subTest(event_type=event_type):
                client = FakeHermesClient(
                    [
                        HermesEvent(
                            run_id="hermes-run-1",
                            event_type=event_type,
                            error="terminal event",
                        )
                    ]
                )
                executor = HermesExecutor(client=client)
                execution_id = executor.submit(self.job)

                events = list(executor.stream_events(execution_id))

                self.assertEqual(events[-1].event_type, expected_type)
                self.assertEqual(events[-1].error, "terminal event")

    def test_hermes_is_not_default_or_registered_as_active(self):
        default_service = LightningService()
        hermes_service = LightningService(executor=HermesExecutor())

        self.assertNotIsInstance(default_service.executor, HermesExecutor)
        self.assertIsInstance(
            default_service.executor,
            InMemoryLightningExecutor,
        )
        self.assertFalse(hermes_service.health()["available"])

    def test_injected_hermes_client_is_available_through_service(self):
        client = FakeHermesClient()
        hermes_service = LightningService(executor=HermesExecutor(client))

        self.assertTrue(hermes_service.health()["available"])

    def test_hermes_run_mapping_recovers_from_persistence(self):
        with TemporaryDirectory() as directory:
            path = f"{directory}/hermes-runs.json"
            first_client = FakeHermesClient()
            first = HermesExecutor(
                client=first_client,
                persistence_path=path,
            )
            execution_id = first.submit(self.job)
            run_id = first.run_mapping(execution_id).run_id

            recovered = HermesExecutor(
                client=FakeHermesClient(),
                persistence_path=path,
            )

            self.assertEqual(
                recovered.run_mapping(execution_id).run_id,
                run_id,
            )
            self.assertEqual(
                recovered.get_session(execution_id).job.delegation_id,
                self.job.delegation_id,
            )

    def test_hermes_metrics_track_runs_and_pending_approvals(self):
        client = FakeHermesClient(
            [
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.RUN_STARTED,
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.APPROVAL_REQUEST,
                    approval_id="approval-1",
                ),
                HermesEvent(
                    run_id="hermes-run-1",
                    event_type=HermesEventType.RUN_COMPLETED,
                ),
            ]
        )
        executor = HermesExecutor(client=client)
        execution_id = executor.submit(self.job)
        events = executor.stream_events(execution_id)

        next(events)
        next(events)
        self.assertEqual(executor.metrics()["active_hermes_runs"], 1)
        self.assertEqual(executor.metrics()["pending_approvals"], 1)

        list(events)
        self.assertEqual(executor.metrics()["completed_runs"], 1)
        self.assertEqual(executor.metrics()["pending_approvals"], 0)


if __name__ == "__main__":
    unittest.main()
