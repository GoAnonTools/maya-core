from typing import Any


MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
OFFLINE_MODE = "OFFLINE_MODE"
INVALID_REQUEST = "INVALID_REQUEST"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def make_error_response(code: str, message: str) -> dict[str, Any]:
    """Build the standard Maya error response envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }
