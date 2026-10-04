import os
import unittest
from unittest.mock import patch

from app.delegation import DelegationRequest, DelegationStatus
from app.workers.lightning import (
    LightningSpecialistWorker,
    LightningWorkerConfig,
)


class LightningWorkerTests(unittest.TestCase):
    def test_exposes_placeholder_configuration_and_capabilities(self):
        config = LightningWorkerConfig(
            endpoint="https://placeholder.invalid",
            workspace="test-workspace",
            deployment="test-deployment",
        )
        worker = LightningSpecialistWorker(config)

        capability = worker.capability()

        self.assertEqual(config.workspace, "test-workspace")
        self.assertFalse(capability.availability)
        self.assertEqual(capability.role.value, "specialist")
        self.assertIn("coding", capability.capabilities)

    def test_configuration_can_read_environment_placeholders(self):
        with patch.dict(
            os.environ,
            {
                "MAYA_LIGHTNING_ENDPOINT": "https://placeholder.invalid",
                "MAYA_LIGHTNING_WORKSPACE": "workspace",
                "MAYA_LIGHTNING_DEPLOYMENT": "deployment",
                "MAYA_LIGHTNING_ENABLED": "true",
            },
            clear=False,
        ):
            config = LightningWorkerConfig.from_environment()

        self.assertEqual(config.endpoint, "https://placeholder.invalid")
        self.assertEqual(config.workspace, "workspace")
        self.assertEqual(config.deployment, "deployment")
        self.assertTrue(config.enabled)

    def test_lifecycle_emits_structured_placeholder_events(self):
        worker = LightningSpecialistWorker()
        request = DelegationRequest("lightning-1", "Inspect code")

        worker.start()
        execution_id = worker.submit(request)
        events = list(worker.stream_events(execution_id))

        self.assertEqual(
            [event.status for event in events],
            [DelegationStatus.STARTED, DelegationStatus.FAILED],
        )
        self.assertIn("not implemented", events[-1].error)

        worker.shutdown()
        with self.assertRaises(RuntimeError):
            worker.submit(request)

    def test_cancellation_is_reported(self):
        worker = LightningSpecialistWorker()
        request = DelegationRequest("lightning-cancel", "Inspect code")

        worker.start()
        execution_id = worker.submit(request)
        worker.cancel(execution_id)
        events = list(worker.stream_events(execution_id))

        self.assertEqual(events[-1].status, DelegationStatus.CANCELLED)
