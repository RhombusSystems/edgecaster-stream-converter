"""MediaMTX integration helpers."""

from __future__ import annotations


def build_rtsp_publish_url(host: str, port: int, path: str) -> str:
    """Build the RTSP URL that FFmpeg publishes to on MediaMTX."""
    return f"rtsp://{host}:{port}/{path}"


def build_rtsp_playback_url(device_ip: str, port: int, path: str) -> str:
    """Build the external RTSP URL that consumers connect to."""
    return f"rtsp://{device_ip}:{port}/{path}"
