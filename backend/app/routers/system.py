"""System status routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.dependencies import get_config, get_discovery, get_stream_manager
from backend.app.models.settings import SystemStatus
from backend.app.services.health import get_system_status
from backend.app.services.posthog_service import get_device_id

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status() -> SystemStatus:
    """Return system health metrics."""
    config = get_config()
    discovery = get_discovery()
    stream_mgr = get_stream_manager()

    return get_system_status(
        total_cameras=len(discovery.cameras),
        active_streams=stream_mgr.active_count,
        max_streams=config.max_streams,
    )


@router.get("/posthog-config")
async def posthog_config() -> dict:
    """Return PostHog configuration for the frontend SDK."""
    config = get_config()
    return {
        "api_key": config.posthog_api_key,
        "host": config.posthog_host,
        "device_id": get_device_id(),
    }
