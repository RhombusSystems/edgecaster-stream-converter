"""Settings routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.config import save_config
from backend.app.dependencies import (
    get_config,
    get_discovery,
    get_rhombus_client,
    get_stream_manager,
    set_rhombus_client,
)
from backend.app.models.settings import AppSettings, SetupState
from backend.app.services.rhombus_api import RhombusClient
from backend.app.utils.network import get_hostname, get_local_ip

logger = logging.getLogger("edgecaster")

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    api_key: str



@router.get("")
async def get_settings() -> AppSettings:
    """Return current application settings (no secrets)."""
    config = get_config()

    if not config.api_key:
        setup_state = SetupState.NEEDS_API_KEY
    else:
        setup_state = SetupState.READY

    return AppSettings(
        hostname=get_hostname(),
        local_ip=get_local_ip(),
        api_key_configured=bool(config.api_key),
        setup_state=setup_state,
        max_streams=config.max_streams,
        mediamtx_rtsp_port=config.mediamtx_rtsp_port,
    )


@router.post("/api-key")
async def set_api_key(req: ApiKeyRequest) -> dict:
    """Save or update the Rhombus Org API Key."""
    config = get_config()

    if not req.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key cannot be empty.",
        )

    # Validate the key by making a test API call
    test_client = RhombusClient(req.api_key.strip())
    try:
        valid = await test_client.validate_api_key()
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key validation failed. Check your key and try again.",
            )
    except Exception as e:
        await test_client.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to validate API key: {e}",
        ) from e

    # Save the key
    config.api_key = req.api_key.strip()
    save_config(config)

    # Update the global Rhombus client
    old_client = get_rhombus_client()
    if old_client:
        await old_client.close()

    new_client = RhombusClient(config.api_key)
    set_rhombus_client(new_client)
    get_stream_manager().set_rhombus_client(new_client)

    # Auto-discover cameras
    try:
        await get_discovery().refresh(new_client)
    except Exception as e:
        logger.warning("Auto-discovery after API key update failed: %s", e)

    logger.info("API key updated successfully")
    return {"ok": True}


@router.post("/discovery/refresh")
async def refresh_discovery() -> dict:
    """Manually trigger camera discovery."""
    client = get_rhombus_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key not configured. Set an API key first.",
        )

    cameras = await get_discovery().refresh(client)
    return {"ok": True, "count": len(cameras)}
