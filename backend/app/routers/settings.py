"""Settings routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.config import save_config
from backend.app.dependencies import (
    get_alert_manager,
    get_config,
    get_discovery,
    get_rhombus_client,
    get_stream_manager,
    get_tunnel_manager,
    set_rhombus_client,
)
from backend.app.models.settings import AppSettings, SetupState
from backend.app.services.auth import hash_password
from backend.app.services.posthog_service import capture_event
from backend.app.services.rhombus_api import RhombusClient
from backend.app.utils.network import get_hostname, get_local_ip

logger = logging.getLogger("edgecaster")

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    api_key: str


class UpdateScheduleRequest(BaseModel):
    auto_update_enabled: bool
    update_hour_start: int
    update_hour_end: int


class AlertSettingsRequest(BaseModel):
    alerts_enabled: bool
    alert_webhook_url: str = ""
    cpu_alert_threshold: int = 85
    temp_alert_threshold_c: int = 80
    load_alert_threshold: float = 0


class PublicCredentialsRequest(BaseModel):
    username: str
    password: str


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
        auto_update_enabled=config.auto_update_enabled,
        update_hour_start=config.update_hour_start,
        update_hour_end=config.update_hour_end,
        alerts_enabled=config.alerts_enabled,
        alert_webhook_url=config.alert_webhook_url,
        cpu_alert_threshold=config.cpu_alert_threshold,
        temp_alert_threshold_c=config.temp_alert_threshold_c,
        load_alert_threshold=config.load_alert_threshold,
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
    capture_event("api_key_configured")
    return {"ok": True}


@router.put("/update-schedule")
async def set_update_schedule(req: UpdateScheduleRequest) -> dict:
    """Configure the auto-update window."""
    if not (0 <= req.update_hour_start <= 23) or not (0 <= req.update_hour_end <= 23):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hours must be between 0 and 23.",
        )

    config = get_config()
    config.auto_update_enabled = req.auto_update_enabled
    config.update_hour_start = req.update_hour_start
    config.update_hour_end = req.update_hour_end
    save_config(config)

    logger.info(
        "Update schedule changed: enabled=%s, window=%02d:00-%02d:00",
        config.auto_update_enabled,
        config.update_hour_start,
        config.update_hour_end,
    )
    return {"ok": True}


@router.put("/alerts")
async def set_alert_settings(req: AlertSettingsRequest) -> dict:
    """Configure LAN webhook alerting and thresholds."""
    if min(req.cpu_alert_threshold, req.temp_alert_threshold_c, req.load_alert_threshold) < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thresholds must be non-negative.",
        )

    config = get_config()
    config.alerts_enabled = req.alerts_enabled
    config.alert_webhook_url = req.alert_webhook_url.strip()
    config.cpu_alert_threshold = req.cpu_alert_threshold
    config.temp_alert_threshold_c = req.temp_alert_threshold_c
    config.load_alert_threshold = req.load_alert_threshold
    save_config(config)

    logger.info(
        "Alert settings updated: enabled=%s, webhook=%s",
        config.alerts_enabled,
        "set" if config.alert_webhook_url else "unset",
    )
    return {"ok": True}


@router.post("/alerts/test")
async def test_alert() -> dict:
    """Send a test alert to the configured webhook."""
    config = get_config()
    if not config.alert_webhook_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No webhook URL configured. Save a webhook URL first.",
        )
    ok = await get_alert_manager().send_test()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to deliver test alert. Check the webhook URL and device network.",
        )
    return {"ok": True}


@router.get("/public-access")
async def get_public_access() -> dict:
    """Return public-access (Cloudflare tunnel) status."""
    return get_tunnel_manager().status()


@router.post("/public-access/credentials")
async def set_public_credentials(req: PublicCredentialsRequest) -> dict:
    """Set the username/password required to reach the public URL."""
    username = req.username.strip()
    if not username or not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are both required.",
        )
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    config = get_config()
    config.auth_username = username
    config.auth_password_hash = hash_password(req.password)
    save_config(config)
    logger.info("Public-access credentials set for user '%s'", username)
    return {"ok": True}


@router.post("/public-access/enable")
async def enable_public_access() -> dict:
    """Start the Cloudflare tunnel and return the public URL."""
    config = get_config()
    tunnel = get_tunnel_manager()

    if not (config.auth_username and config.auth_password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set a username and password before enabling public access.",
        )
    if not tunnel.is_installed():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cloudflared is not installed on this device.",
        )

    config.public_access_enabled = True
    save_config(config)
    try:
        await tunnel.start()
    except Exception as e:  # noqa: BLE001
        config.public_access_enabled = False
        save_config(config)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to start the tunnel: {e}",
        ) from e

    url = await tunnel.wait_for_url(timeout=25)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Tunnel started but no public URL yet. Check status in a moment.",
        )
    logger.info("Public access enabled: %s", url)
    return tunnel.status()


@router.post("/public-access/disable")
async def disable_public_access() -> dict:
    """Stop the Cloudflare tunnel; the device stays reachable on the LAN."""
    config = get_config()
    config.public_access_enabled = False
    save_config(config)
    await get_tunnel_manager().stop()
    logger.info("Public access disabled")
    return get_tunnel_manager().status()


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
    capture_event("discovery_completed", {"camera_count": len(cameras)})
    return {"ok": True, "count": len(cameras)}
