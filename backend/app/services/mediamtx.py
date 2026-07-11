"""MediaMTX integration helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("edgecaster.mediamtx")

_API_TIMEOUT = 3.0


def build_rtsp_publish_url(host: str, port: int, path: str) -> str:
    """Build the RTSP URL that FFmpeg publishes to on MediaMTX."""
    return f"rtsp://{host}:{port}/{path}"


def build_rtsp_playback_url(device_ip: str, port: int, path: str) -> str:
    """Build the external RTSP URL that consumers connect to."""
    return f"rtsp://{device_ip}:{port}/{path}"


@dataclass
class PathStats:
    """Per-path stats from the MediaMTX control API."""

    ready: bool = False
    bytes_received: int = 0
    bytes_sent: int = 0
    readers: int = 0


async def get_path_stats(host: str, port: int) -> dict[str, PathStats]:
    """Fetch per-path liveness/throughput stats from the MediaMTX control API.

    Returns a dict of path_name -> PathStats. Returns an empty dict on any
    error (API disabled, MediaMTX down) so callers can degrade gracefully.
    """
    url = f"http://{host}:{port}/v3/paths/list"
    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001 - best-effort, never fatal
        logger.debug("MediaMTX API query failed (%s): %s", url, e)
        return {}

    result: dict[str, PathStats] = {}
    for item in data.get("items", []):
        name = item.get("name")
        if not name:
            continue
        result[name] = PathStats(
            ready=bool(item.get("ready", False)),
            bytes_received=int(item.get("bytesReceived", 0) or 0),
            bytes_sent=int(item.get("bytesSent", 0) or 0),
            readers=len(item.get("readers", []) or []),
        )
    return result
