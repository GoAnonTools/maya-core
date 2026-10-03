from fastapi import FastAPI
from datetime import datetime, timezone
import os

from app.identity import load_identity
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
