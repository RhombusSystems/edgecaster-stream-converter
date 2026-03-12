"""Stream management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.dependencies import get_discovery, get_stream_manager, require_auth
from backend.app.models.stream import StreamInfo

router = APIRouter(prefix="/api/streams", tags=["streams"], dependencies=[Depends(require_auth)])


@router.get("")
async def list_streams() -> list[StreamInfo]:
    """Return all active/managed streams."""
    return get_stream_manager().get_all_stream_info()


@router.post("/{camera_uuid}/enable")
async def enable_stream(camera_uuid: str) -> StreamInfo:
    """Enable RTSP streaming for a camera."""
    discovery = get_discovery()
    stream_mgr = get_stream_manager()

    camera = discovery.get_camera(camera_uuid)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_uuid} not found. Try refreshing discovery.",
        )

    try:
        return await stream_mgr.start_stream(camera_uuid, camera.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e


@router.post("/{camera_uuid}/disable")
async def disable_stream(camera_uuid: str) -> dict:
    """Disable RTSP streaming for a camera."""
    await get_stream_manager().stop_stream(camera_uuid)
    return {"ok": True}
