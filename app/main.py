from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import os
from typing import Union

from app.context import create_request_context
from app.errors import (
    INVALID_REQUEST,
    MODEL_UNAVAILABLE,
    OFFLINE_MODE,
    SERVICE_UNAVAILABLE,
    make_error_response,
)
from app.identity import load_identity
from app.model_client import send_prompt, stream_prompt
from app.memory_client import store_memory
from app.orchestration import NormalizedRequest, Orchestrator
from app.router import select_model
from app.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.settings import get_public_settings, load_settings
from app.workers.catalog import create_worker_catalog


MAYA_VERSION = "0.1.0"


app = FastAPI(
    title="Maya Core",
    version=MAYA_VERSION,
    description="Maya Core Router — identity, routing, permissions"
)


def get_mode():
    """
    Future:
    - check Hermes availability
    - check Lightning health
    - switch offline mode
    """
    return os.getenv("MAYA_MODE", "online")


def get_orchestrator() -> Orchestrator:
    """Build the execution boundary around the current default worker."""
    worker_registry = create_worker_catalog(
        send_prompt_fn=send_prompt,
        stream_prompt_fn=stream_prompt,
    )
    return Orchestrator(worker_registry, default_worker_id="default")


@app.get("/health")
def health():
    return {
        "name": "Maya Core",
        "status": "online",
        "version": MAYA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": get_mode(),
        "services": {
            "model": "not_connected",
            "memory": "not_connected",
            "agent_os": "disabled"
        }
    }


@app.get("/identity")
def get_identity():
    return load_identity()


@app.get("/config/status")
def get_config_status():
    return get_public_settings(load_settings())


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content=make_error_response(
            INVALID_REQUEST,
            "The request body is invalid.",
        ),
    )


@app.post("/chat", response_model=Union[ChatResponse, ErrorResponse])
def chat(request: ChatRequest):
    if not request.message.strip():
        return JSONResponse(
            status_code=400,
            content=make_error_response(
                INVALID_REQUEST,
                "message must not be empty",
            ),
        )

    context = create_request_context(request.message)

    if request.message.lower().startswith("remember "):
        memory_text = request.message[9:].strip()

        store_memory(
            "user_memory",
            memory_text,
            8,
        )

    route = select_model()
    request_context = NormalizedRequest(context=context, route=route)
    result = get_orchestrator().execute(request_context)

    if result["status"] == "unavailable":
        if route["mode"] == "offline":
            return JSONResponse(
                status_code=503,
                content=make_error_response(
                    OFFLINE_MODE,
                    "Maya is running in limited offline mode.",
                ),
            )

        return JSONResponse(
            status_code=503,
            content=make_error_response(
                MODEL_UNAVAILABLE,
                "The selected model is unavailable.",
            ),
        )

    if result["status"] == "not_connected":
        return JSONResponse(
            status_code=503,
            content=make_error_response(
                SERVICE_UNAVAILABLE,
                "The model service is not connected.",
            ),
        )

    return {
        "response": result["message"],
        "model": route["model"],
        "mode": route["mode"],
        "timestamp": datetime.now(timezone.utc),
    }


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    if not request.message.strip():
        return JSONResponse(
            status_code=400,
            content=make_error_response(
                INVALID_REQUEST,
                "message must not be empty",
            ),
        )

    context = create_request_context(request.message)

    if request.message.lower().startswith("remember "):
        memory_text = request.message[9:].strip()

        store_memory(
            "user_memory",
            memory_text,
            8,
        )

    route = select_model()
    request_context = NormalizedRequest(context=context, route=route)
    orchestrator = get_orchestrator()

    def generate():
        try:
            for chunk in orchestrator.stream(request_context):
                yield f"data: {chunk}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
