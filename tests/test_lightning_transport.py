import unittest

from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
    LightningWorkerConfig,
)
from app.workers.lightning_transport import (
    LightningRemoteClient,
    LightningTransport,
)


class FakeLightningTransport(LightningTransport):
    def __init__(self):
        self.connected_config = None
        self.closed = False
        self.submitted = []
        self.cancelled = []

    def connect(self, config):
        self.connected_config = config
        self.closed = False

    def submit(self, job):
        self.submitted.append(job)
        return f"remote-{job.delegation_id}"

    def stream_events(self, execution_id):
        yield LightningEvent(
            delegation_id=execution_id,
            event_type=LightningEventType.STARTED,
        )
        yield LightningEvent(
            delegation_id=execution_id,
            event_type=LightningEventType.PROGRESS,
            progress=0.5,
        )

    def cancel(self, execution_id):
        self.cancelled.append(execution_id)

    def close(self):
        self.closed = True


class LightningTransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeLightningTransport()
        self.config = LightningWorkerConfig(workspace="test-workspace")
        self.client = LightningRemoteClient(self.transport, self.config)
        self.job = LightningJob(
            delegation_id="delegation-1",
            request_id="request-1",
            session_id="session-1",
            workspace="test-workspace",
            capabilities=frozenset({"coding"}),
        )

    def test_connection_lifecycle(self):
        self.assertFalse(self.client.connected)

        self.client.start()
        self.client.start()

        self.assertTrue(self.client.connected)
        self.assertIs(self.transport.connected_config, self.config)

        self.client.shutdown()
        self.client.shutdown()

        self.assertFalse(self.client.connected)
        self.assertTrue(self.transport.closed)

    def test_submit_and_stream_events(self):
        self.client.start()

        execution_id = self.client.submit(self.job)
        events = list(self.client.stream_events(execution_id))

        self.assertEqual(execution_id, "remote-delegation-1")
        self.assertEqual(self.transport.submitted, [self.job])
        self.assertEqual(
            [event.event_type for event in events],
            [LightningEventType.STARTED, LightningEventType.PROGRESS],
        )

    def test_cancellation_is_forwarded(self):
        self.client.start()

        self.client.cancel("remote-delegation-1")

        self.assertEqual(self.transport.cancelled, ["remote-delegation-1"])

    def test_operations_require_connection(self):
        with self.assertRaises(RuntimeError):
            self.client.submit(self.job)

        with self.assertRaises(RuntimeError):
            list(self.client.stream_events("execution"))

        with self.assertRaises(RuntimeError):
            self.client.cancel("execution")

    def test_transport_contract_is_abstract(self):
        with self.assertRaises(TypeError):
            LightningTransport()
