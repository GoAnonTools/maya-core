"""Read-only HTTP observability boundary for delegation execution."""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.delegation.manager import DelegationManager
from app.delegation.repository_workflow import RepositoryAnalysisWorkflow


def create_delegation_observability_app(
    manager: DelegationManager,
) -> FastAPI:
    """Create the read-only delegation observability API."""
    application = FastAPI(
        title="Maya Delegation Observability",
        version="0.1.0",
        description="Read-only delegation status, audit, and event boundary",
    )
    application.state.delegation_manager = manager

    @application.get("/delegations/{delegation_id}/status")
    def status(delegation_id: str) -> dict[str, Any]:
        _require(manager, delegation_id)
        pending = None
        try:
            pending = manager.get_pending_approval(delegation_id)
        except KeyError:
            pass
        return {
            "delegation_id": delegation_id,
            "status": manager.get_status(delegation_id).value,
            "pending_approval": _jsonable(pending),
        }

    @application.get("/delegations/{delegation_id}/timeline")
    def timeline(delegation_id: str) -> dict[str, Any]:
        record = _record(manager, delegation_id)
        return {
            "delegation_id": delegation_id,
            "timeline": _jsonable(record.timeline),
        }

    @application.get("/delegations/{delegation_id}/audit")
    def audit(delegation_id: str) -> dict[str, Any]:
        record = _record(manager, delegation_id)
        return {
            "summary": _jsonable(record.summary()),
            "operator_summary": record.operator_summary(),
        }

    @application.get("/delegations/{delegation_id}/events")
    def events(delegation_id: str):
        _require(manager, delegation_id)

        async def generate():
            for event in manager.events(delegation_id):
                payload = _jsonable(event)
                yield (
                    f"event: {event.event_type.value}\n"
                    f"data: {json.dumps(payload, sort_keys=True)}\n\n"
                )

        return StreamingResponse(generate(), media_type="text/event-stream")

    return application


def register_repository_analysis_routes(
    application: FastAPI,
    workflow: RepositoryAnalysisWorkflow | None,
) -> None:
    """Register the explicit user-facing read-only workflow endpoints."""

    @application.post("/delegations/repository-analysis")
    def create_repository_analysis(payload: dict[str, Any] | None = None):
        if workflow is None:
            raise HTTPException(
                status_code=503,
                detail="Hermes is disabled. Enable it explicitly before starting repository analysis.",
            )
        body = payload or {}
        return _jsonable(workflow.create(workspace=body.get("workspace")))

    @application.post("/delegations/{delegation_id}/approve")
    def approve_repository_analysis(delegation_id: str, payload: dict[str, Any]):
        if workflow is None:
            raise HTTPException(status_code=503, detail="Hermes is disabled.")
        approval_id = str(payload.get("approval_id", "")).strip()
        if not approval_id:
            raise HTTPException(status_code=400, detail="approval_id is required")
        try:
            return _jsonable(workflow.approve(delegation_id, approval_id))
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


def _require(manager: DelegationManager, delegation_id: str) -> None:
    try:
        manager.get_status(delegation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _record(manager: DelegationManager, delegation_id: str):
    _require(manager, delegation_id)
    return manager.execution_record(delegation_id)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value
