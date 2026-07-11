"""Configuration management for EdgeCaster."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

# Production paths
PROD_CONFIG_PATH = Path("/etc/edgecaster/config.yaml")
PROD_STATE_DIR = Path("/var/lib/edgecaster")
PROD_LOG_DIR = Path("/var/log/edgecaster")

# Dev fallback paths (relative to project root)
DEV_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEV_CONFIG_PATH = DEV_DATA_DIR / "config.yaml"
DEV_STATE_DIR = DEV_DATA_DIR
DEV_LOG_DIR = DEV_DATA_DIR / "logs"


def _is_dev_mode() -> bool:
    return os.environ.get("EDGECASTER_ENV", "dev") != "production"


class EdgeCasterConfig(BaseModel):
    """Runtime configuration loaded from YAML."""

    api_key: str = ""
    # 0 = unlimited (run as many streams as the device can handle).
    # A positive value acts as an optional hard safety ceiling.
    max_streams: int = 0
    mediamtx_rtsp_port: int = 8554
    mediamtx_host: str = "127.0.0.1"
    mediamtx_api_host: str = "127.0.0.1"
    mediamtx_api_port: int = 9997
    ffmpeg_loglevel: str = "warning"

    # Low-latency FFmpeg tuning (on-device tunable without a code change)
    ffmpeg_probesize: int = 500000  # bytes; lower = faster start, too low fails SPS/PPS detection
    ffmpeg_analyzeduration: int = 1000000  # microseconds
    ffmpeg_rw_timeout: int = 5000000  # microseconds; abort input if no data for this long

    # Frame-level stall detection: restart a stream whose output has not
    # advanced for this many seconds (independent of process liveness).
    stall_threshold_seconds: int = 6

    auto_update_enabled: bool = True
    update_hour_start: int = 2
    update_hour_end: int = 5

    # LAN alerting (generic webhook: Slack/Make/custom listener)
    alerts_enabled: bool = False
    alert_webhook_url: str = ""
    cpu_alert_threshold: int = 85  # percent, sustained
    temp_alert_threshold_c: int = 80  # degrees Celsius
    load_alert_threshold: float = 0  # 1-min load average; 0 = disabled

    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"

    # Resolved at load time, not persisted
    config_path: Path = Path(".")
    state_dir: Path = Path(".")
    log_dir: Path = Path(".")
    dev_mode: bool = True


def load_config() -> EdgeCasterConfig:
    """Load configuration from YAML file with dev/production path resolution."""
    dev_mode = _is_dev_mode()

    if dev_mode:
        config_path = DEV_CONFIG_PATH
        state_dir = DEV_STATE_DIR
        log_dir = DEV_LOG_DIR
    else:
        config_path = PROD_CONFIG_PATH
        state_dir = PROD_STATE_DIR
        log_dir = PROD_LOG_DIR

    # Ensure directories exist
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    config = EdgeCasterConfig(
        config_path=config_path,
        state_dir=state_dir,
        log_dir=log_dir,
        dev_mode=dev_mode,
        **{k: v for k, v in data.items() if k in EdgeCasterConfig.model_fields},
    )
    return config


def save_config(config: EdgeCasterConfig) -> None:
    """Persist configuration back to YAML."""
    data = {
        "api_key": config.api_key,
        "max_streams": config.max_streams,
        "mediamtx_rtsp_port": config.mediamtx_rtsp_port,
        "mediamtx_host": config.mediamtx_host,
        "mediamtx_api_host": config.mediamtx_api_host,
        "mediamtx_api_port": config.mediamtx_api_port,
        "ffmpeg_loglevel": config.ffmpeg_loglevel,
        "ffmpeg_probesize": config.ffmpeg_probesize,
        "ffmpeg_analyzeduration": config.ffmpeg_analyzeduration,
        "ffmpeg_rw_timeout": config.ffmpeg_rw_timeout,
        "stall_threshold_seconds": config.stall_threshold_seconds,
        "auto_update_enabled": config.auto_update_enabled,
        "update_hour_start": config.update_hour_start,
        "update_hour_end": config.update_hour_end,
        "alerts_enabled": config.alerts_enabled,
        "alert_webhook_url": config.alert_webhook_url,
        "cpu_alert_threshold": config.cpu_alert_threshold,
        "temp_alert_threshold_c": config.temp_alert_threshold_c,
        "load_alert_threshold": config.load_alert_threshold,
        "posthog_api_key": config.posthog_api_key,
        "posthog_host": config.posthog_host,
    }
    _save_raw_config(config.config_path, data)


def _save_raw_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
