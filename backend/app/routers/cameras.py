"""Camera discovery routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.dependencies import get_discovery, get_stream_manager
from backend.app.models.camera import Camera

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


class CameraResponse(Camera):
    """Camera with stream-related fields."""

    rtsp_enabled: bool = False
    rtsp_url: str = ""
    stream_state: str = ""


@router.get("")
async def list_cameras() -> list[CameraResponse]:
    """Return all discovered cameras with their stream state."""
    discovery = get_discovery()
    stream_mgr = get_stream_manager()

    result = []
    for cam in discovery.cameras:
        stream_info = stream_mgr.get_stream_info(cam.uuid)
        result.append(
            CameraResponse(
                **cam.model_dump(),
                rtsp_enabled=stream_mgr.is_enabled(cam.uuid),
                rtsp_url=stream_info.rtsp_url if stream_info else "",
                stream_state=stream_info.state.value if stream_info else "",
            )
        )
    return result
