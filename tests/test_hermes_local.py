import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from app.delegation import (
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
    OptInHermesExecutorSelector,
)
from app.delegation.policy import HermesDelegationPolicy
from app.services.hermes_config import HermesLocalConfig
from app.services.hermes_local import build_local_hermes_executor
from app.services.lightning_executor import InMemoryLightningExecutor
from tests.fake_hermes_service import FakeHermesService


class HermesLocalConfigurationTests(unittest.TestCase):
    def test_disabled_configuration_needs_no_endpoint(self):
        config = HermesLocalConfig()

        self.assertIs(config.validate(), config)
        self.assertFalse(config.enabled)

    def test_enabled_configuration_requires_absolute_endpoint(self):
        with self.assertRaisesRegex(ValueError, "ENDPOINT is required"):
            HermesLocalConfig(enabled=True).validate()

        with self.assertRaisesRegex(ValueError, r"absolute http\(s\) URL"):
            HermesLocalConfig(
                enabled=True,
                endpoint="localhost:8765",
            ).validate()

    def test_environment_configuration_is_explicitly_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(HermesLocalConfig.from_environment().enabled)

        with patch.dict(
            os.environ,
            {
                "MAYA_HERMES_ENABLED": "true",
                "MAYA_HERMES_ENDPOINT": "http://127.0.0.1:8765",
            },
        ):
            config = HermesLocalConfig.from_environment()
            self.assertTrue(config.validate().enabled)

    def test_environment_configuration_reads_minimal_permissions(self):
        with patch.dict(
            os.environ,
            {
                "MAYA_HERMES_ENABLED": "true",
                "MAYA_HERMES_ENDPOINT": "http://127.0.0.1:8765",
                "MAYA_HERMES_PERMISSIONS": "read_only, filesystem_read",
            },
        ):
            config = HermesLocalConfig.from_environment()

        self.assertEqual(
            config.permissions,
            frozenset({"read_only", "filesystem_read"}),
        )

    def test_disabled_factory_does_not_create_a_client(self):
        executor = build_local_hermes_executor(
            object(),
            config=HermesLocalConfig(enabled=False),
        )

        self.assertFalse(executor.is_available())
        self.assertIsNone(executor.client)

    def test_enabled_factory_integrates_health_check(self):
        service = FakeHermesService()
        client = service.client()
        try:
            executor = build_local_hermes_executor(
                client,
                config=HermesLocalConfig(
                    enabled=True,
                    endpoint="https://fake/api",
                    permissions=frozenset({"read_only"}),
                ),
            )

            health = executor.health()
            self.assertTrue(health["available"])
            self.assertTrue(health["client"]["available"])
            self.assertEqual(
                executor.capabilities().required_permissions,
                frozenset({"read_only"}),
            )
        finally:
            client.close()


@unittest.skipUnless(
    os.getenv("MAYA_HERMES_SMOKE_TEST", "false").lower()
    in {"1", "true", "yes"}
    and os.getenv("MAYA_HERMES_ENABLED", "false").lower()
    in {"1", "true", "yes"}
    and bool(os.getenv("MAYA_HERMES_ENDPOINT")),
    "Set MAYA_HERMES_ENABLED=true, MAYA_HERMES_SMOKE_TEST=true, and "
    "MAYA_HERMES_ENDPOINT to run",
)
class HermesLocalSmokeTests(unittest.TestCase):
    def test_real_local_hermes_health_endpoint(self):
        config = HermesLocalConfig.from_environment().validate()
        with httpx.Client() as client:
            executor = build_local_hermes_executor(client, config=config)
            health = executor.health()

        self.assertTrue(health["available"])

    def test_real_local_read_only_research_execution(self):
        """Run one explicitly approved task against the configured endpoint."""
        config = HermesLocalConfig.from_environment().validate()
        with TemporaryDirectory() as directory, httpx.Client() as client:
            executor = build_local_hermes_executor(
                client,
                config=config,
                persistence_path=f"{directory}/hermes-runs.json",
            )
            selector = OptInHermesExecutorSelector(
                hermes_executor=executor,
                fallback_executor=InMemoryLightningExecutor(),
                policy=HermesDelegationPolicy(enabled=True),
            )
            manager = DelegationManager(
                persistence_path=f"{directory}/delegations.json",
                audit_path=f"{directory}/execution-audit.json",
            )
            request = DelegationRequest(
                delegation_id="real-local-research",
                task="Research the Maya architecture using read-only sources.",
                metadata={
                    "task_category": "research",
                    "requires_approval": True,
                    "approval_id": "real-local-research-approval",
                    "dangerous": False,
                    "granted_permissions": ["read_only"],
                },
            )

            waiting = manager.execute_with_executor(
                request,
                selector=selector,
            )
            self.assertEqual(
                waiting[-1].status,
                DelegationStatus.WAITING_APPROVAL,
            )
            manager.approve(
                "real-local-research",
                "real-local-research-approval",
            )

            events = manager.execute_with_executor(
                request,
                selector=selector,
            )
            health = executor.health()

        self.assertTrue(health["available"])
        self.assertEqual(events[-1].status, DelegationStatus.COMPLETED)
        self.assertGreaterEqual(len(events), 5)
        audit = manager.execution_record("real-local-research")
        self.assertEqual(audit.executor_selected, "hermes")
        self.assertEqual(audit.policy_recommendation, "candidate")
        self.assertEqual(audit.approval_state, "approved")
        self.assertEqual(audit.terminal_status, "completed")


if __name__ == "__main__":
    unittest.main()
