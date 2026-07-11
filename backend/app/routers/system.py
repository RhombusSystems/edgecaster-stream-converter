"""System status routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.app.dependencies import (
    get_config,
    get_discovery,
    get_metrics_collector,
    get_stream_manager,
)
from backend.app.models.settings import SystemStatus
from backend.app.services.health import get_system_status
from backend.app.services.posthog_service import get_device_id

router = APIRouter(prefix="/api/system", tags=["system"])

_SSE_INTERVAL = 1  # seconds between pushes


def _current_status() -> SystemStatus:
    """Return the freshest cached snapshot, or a blocking sample as fallback."""
    collector = get_metrics_collector()
    if collector.latest is not None:
        return collector.latest
    config = get_config()
    return get_system_status(
        total_cameras=len(get_discovery().cameras),
        active_streams=get_stream_manager().active_count,
        max_streams=config.max_streams,
    )


@router.get("/status")
async def system_status() -> SystemStatus:
    """Return system health metrics (polling fallback)."""
    return _current_status()


@router.get("/stream")
async def system_stream(request: Request) -> StreamingResponse:
    """Push live system metrics + active alerts to the dashboard over SSE."""

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: {_current_status().model_dump_json()}\n\n"
            await asyncio.sleep(_SSE_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx proxy buffering
        },
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
