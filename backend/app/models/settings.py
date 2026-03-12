"""Settings and system status models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SetupState(str, Enum):
    NEEDS_PASSWORD = "needs_password"
    NEEDS_API_KEY = "needs_api_key"
    READY = "ready"


class AppSettings(BaseModel):
    """Public-facing settings (no secrets)."""

    hostname: str = ""
    local_ip: str = ""
    api_key_configured: bool = False
    setup_state: SetupState = SetupState.NEEDS_PASSWORD
    max_streams: int = 10
    mediamtx_rtsp_port: int = 8554


class SystemStatus(BaseModel):
    """System health information."""

    hostname: str = ""
    local_ip: str = ""
    uptime_seconds: float = 0
    cpu_percent: float = 0
    memory_percent: float = 0
    total_cameras: int = 0
    active_streams: int = 0
    max_streams: int = 10
