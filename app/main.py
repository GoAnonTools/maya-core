from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
from app.model_client import send_prompt
from app.router import select_model
from app.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.settings import get_public_settings, load_settings


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
    route = select_model()
    result = send_prompt(context, route)

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
