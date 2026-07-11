"""Settings and system status models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SetupState(str, Enum):
    NEEDS_API_KEY = "needs_api_key"
    READY = "ready"


class AppSettings(BaseModel):
    """Public-facing settings (no secrets)."""

    hostname: str = ""
    local_ip: str = ""
    api_key_configured: bool = False
    setup_state: SetupState = SetupState.NEEDS_API_KEY
    max_streams: int = 0
    mediamtx_rtsp_port: int = 8554
    auto_update_enabled: bool = True
    update_hour_start: int = 2
    update_hour_end: int = 5
    # Alerting (LAN-local; exposed for editing, consistent with no-LAN-auth design)
    alerts_enabled: bool = False
    alert_webhook_url: str = ""
    cpu_alert_threshold: int = 85
    temp_alert_threshold_c: int = 80
    load_alert_threshold: float = 0


class Alert(BaseModel):
    """An active alert condition."""

    type: str  # e.g. "under_voltage", "thermal", "high_cpu", "stream_down"
    severity: str  # "critical" | "warning"
    title: str = ""
    message: str = ""
    since: float = 0  # epoch seconds when the condition became active


class SystemStatus(BaseModel):
    """System health information."""

    hostname: str = ""
    local_ip: str = ""
    uptime_seconds: float = 0
    cpu_percent: float = 0
    memory_percent: float = 0
    total_cameras: int = 0
    active_streams: int = 0
    max_streams: int = 0
    # Raspberry Pi strain metrics (best-effort; defaults if unavailable)
    temperature_c: float = 0
    throttle_status: str = "unknown"  # "ok" | "under_voltage" | "throttled" | "unknown"
    under_voltage_now: bool = False
    under_voltage_occurred: bool = False
    throttled_now: bool = False
    throttled_occurred: bool = False
    freq_capped_now: bool = False
    load_avg_1m: float = 0
    load_avg_5m: float = 0
    load_avg_15m: float = 0
    cpu_count: int = 0
    cpu_freq_mhz: float = 0
    # Currently-active alert conditions
    alerts: list[Alert] = []
