"""Explicit, opt-in repository-analysis delegation workflow."""

from dataclasses import dataclass
import os
from uuid import uuid4
from typing import Any

import httpx

from app.delegation.executor_selection import OptInHermesExecutorSelector
from app.delegation.manager import DelegationManager
from app.delegation.models import DelegationRequest
from app.delegation.policy import HermesDelegationPolicy
from app.services.hermes_config import HermesLocalConfig
from app.services.hermes_local import build_local_hermes_executor
from app.services.lightning_executor import InMemoryLightningExecutor


READ_ONLY_REPOSITORY_TASK = "Analyze this project structure and provide recommendations."


@dataclass
class RepositoryAnalysisWorkflow:
    manager: DelegationManager
    selector: OptInHermesExecutorSelector

    def create(self, *, workspace: str | None = None) -> dict[str, Any]:
        delegation_id = "repository-analysis-" + uuid4().hex
        request = DelegationRequest(
            delegation_id=delegation_id,
            task=READ_ONLY_REPOSITORY_TASK,
            metadata={
                "task_category": "research",
                "dangerous": False,
                "requires_approval": True,
                "approval_id": delegation_id + "-approval",
                "granted_permissions": ["read_only"],
                "required_permissions": ["read_only"],
                "workspace": workspace or os.getenv("MAYA_WORKSPACE", ""),
                "correlation_id": delegation_id,
            },
        )
        events = self.manager.execute_with_executor(request, selector=self.selector)
        pending = self.manager.get_pending_approval(delegation_id)
        return {
            "delegation_id": delegation_id,
            "status": self.manager.get_status(delegation_id).value,
            "approval_id": pending.approval_id,
            "events": events,
        }

    def approve(self, delegation_id: str, approval_id: str) -> dict[str, Any]:
        request = self.manager.get_request(delegation_id)
        self.manager.approve(delegation_id, approval_id)
        events = self.manager.execute_with_executor(
            request,
            selector=self.selector,
            approval_granted=True,
        )
        return {
            "delegation_id": delegation_id,
            "status": self.manager.get_status(delegation_id).value,
            "events": events,
        }


def create_repository_analysis_workflow() -> RepositoryAnalysisWorkflow | None:
    """Build the workflow only when Hermes is explicitly enabled."""
    config = HermesLocalConfig.from_environment()
    if not config.enabled:
        return None
    config.validate()
    client = httpx.Client()
    executor = build_local_hermes_executor(client, config=config)
    selector = OptInHermesExecutorSelector(
        hermes_executor=executor,
        fallback_executor=InMemoryLightningExecutor(),
        policy=HermesDelegationPolicy(enabled=True),
    )
    return RepositoryAnalysisWorkflow(
        manager=DelegationManager(),
        selector=selector,
    )
