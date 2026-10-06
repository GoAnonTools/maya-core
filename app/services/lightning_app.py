"""Standalone HTTP application boundary for the in-memory Lightning service."""

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.lightning import LightningService
from app.services.lightning_executor import LightningExecutor
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


class LightningJobPayload(BaseModel):
    """HTTP representation of the existing LightningJob protocol model."""

    delegation_id: str
    request_id: str | None = None
    session_id: str | None = None
    workspace: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    status: LightningEventType = LightningEventType.SUBMITTED
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_protocol(self) -> LightningJob:
        return LightningJob(
            delegation_id=self.delegation_id,
            request_id=self.request_id,
            session_id=self.session_id,
            workspace=self.workspace,
            capabilities=frozenset(self.capabilities),
            permissions=frozenset(self.permissions),
            status=self.status,
            metadata=self.metadata,
        )


def create_app(
    executor: LightningExecutor | None = None,
    service: LightningService | None = None,
) -> FastAPI:
    """Create the standalone Lightning service application.

    The service is injected for tests and future process boundaries. No
    network or production worker connection is established here.
    """

    if service is not None and executor is not None:
        raise ValueError("Provide either service or executor, not both")

    lightning_service = service or LightningService(executor=executor)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.started = True
        yield
        application.state.started = False

    application = FastAPI(
        title="Lightning Service",
        version="0.1.0",
        description="In-memory Lightning job protocol service",
        lifespan=lifespan,
    )
    application.state.lightning_service = lightning_service
    application.state.started = False

    @application.get("/health")
    def health(request: Request) -> dict[str, Any]:
        result = request.app.state.lightning_service.health()
        result["started"] = request.app.state.started
        return result

    @application.post("/jobs", status_code=201)
    def submit_job(
        job_payload: LightningJobPayload,
        request: Request,
    ) -> dict[str, str]:
        try:
            execution_id = request.app.state.lightning_service.submit(
                job_payload.to_protocol()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {"execution_id": execution_id}

    @application.get("/jobs/{execution_id}/events")
    def stream_events(execution_id: str, request: Request):
        service_instance = request.app.state.lightning_service
        try:
            service_instance.get_session(execution_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        def generate():
            for event in service_instance.stream_events(execution_id):
                payload = json.dumps(_event_to_dict(event))
                yield f"event: {event.event_type.value}\ndata: {payload}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    @application.post("/jobs/{execution_id}/cancel")
    def cancel_job(execution_id: str, request: Request) -> dict[str, str]:
        try:
            request.app.state.lightning_service.cancel(execution_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {"execution_id": execution_id, "status": "cancelled"}

    return application


def _event_to_dict(event: LightningEvent) -> dict[str, Any]:
    values = asdict(event)
    values["event_type"] = event.event_type.value
    timestamp = values.get("timestamp")
    if isinstance(timestamp, datetime):
        values["timestamp"] = timestamp.isoformat()
    return values


app = create_app()
