import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
    LightningWorkerConfig,
)


class LightningProtocolTests(unittest.TestCase):
    def test_job_contains_identity_scope_and_permissions(self):
        job = LightningJob(
            delegation_id="delegation-1",
            request_id="request-1",
            session_id="session-1",
            workspace="maya-daily",
            capabilities=frozenset({"coding"}),
            permissions=frozenset({"filesystem_read"}),
        )

        self.assertEqual(job.status, LightningEventType.SUBMITTED)
        self.assertEqual(job.workspace, "maya-daily")
        self.assertEqual(job.capabilities, frozenset({"coding"}))
        self.assertEqual(
            job.permissions,
            frozenset({"filesystem_read"}),
        )

    def test_event_supports_lifecycle_and_progress(self):
        event = LightningEvent(
            delegation_id="delegation-1",
            event_type=LightningEventType.PROGRESS,
            request_id="request-1",
            session_id="session-1",
            progress=0.5,
            message="Half complete",
            timestamp=datetime.now(timezone.utc),
        )

        self.assertEqual(event.event_type, LightningEventType.PROGRESS)
        self.assertEqual(event.progress, 0.5)
        self.assertEqual(event.request_id, "request-1")

    def test_config_contains_connection_and_execution_placeholders(self):
        config = LightningWorkerConfig(
            endpoint="https://placeholder.invalid",
            workspace="workspace",
            deployment="deployment",
            capabilities=frozenset({"coding"}),
            permissions=frozenset({"filesystem_read"}),
        )

        self.assertEqual(config.endpoint, "https://placeholder.invalid")
        self.assertEqual(config.workspace, "workspace")
        self.assertEqual(config.deployment, "deployment")
        self.assertFalse(config.enabled)

    def test_config_reads_capabilities_and_permissions_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "MAYA_LIGHTNING_CAPABILITIES": "coding, research",
                "MAYA_LIGHTNING_PERMISSIONS": "filesystem_read",
            },
            clear=False,
        ):
            config = LightningWorkerConfig.from_environment()

        self.assertEqual(
            config.capabilities,
            frozenset({"coding", "research"}),
        )
        self.assertEqual(
            config.permissions,
            frozenset({"filesystem_read"}),
        )

    def test_event_types_cover_required_lifecycle_states(self):
        self.assertEqual(
            {event_type.value for event_type in LightningEventType},
            {
                "submitted",
                "started",
                "progress",
                "completed",
                "failed",
                "cancelled",
            },
        )
