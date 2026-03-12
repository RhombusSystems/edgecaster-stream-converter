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
    max_streams: int = 10
    mediamtx_rtsp_port: int = 8554
    mediamtx_host: str = "127.0.0.1"
    ffmpeg_loglevel: str = "warning"
    auto_update_enabled: bool = True
    update_hour_start: int = 2
    update_hour_end: int = 5

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
        "ffmpeg_loglevel": config.ffmpeg_loglevel,
        "auto_update_enabled": config.auto_update_enabled,
        "update_hour_start": config.update_hour_start,
        "update_hour_end": config.update_hour_end,
    }
    _save_raw_config(config.config_path, data)


def _save_raw_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
