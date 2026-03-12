"""Stream models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class StreamState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


class StreamInfo(BaseModel):
    """Runtime state of a camera stream."""

    camera_uuid: str
    camera_name: str
    rtsp_path: str
    rtsp_url: str
    state: StreamState = StreamState.STOPPED
    error_message: str = ""
    lan_video_url: str = ""
