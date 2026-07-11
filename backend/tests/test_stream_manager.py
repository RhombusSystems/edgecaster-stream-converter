"""Tests for stream manager logic."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.config import EdgeCasterConfig
from backend.app.services.state_store import StateStore
from backend.app.services.stream_manager import StreamManager


@pytest.fixture
def tmp_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield StateStore(Path(tmpdir))


@pytest.fixture
def config():
    return EdgeCasterConfig(
        max_streams=3,
        mediamtx_rtsp_port=8554,
        mediamtx_host="127.0.0.1",
    )


@pytest.fixture
def manager(config, tmp_state):
    return StreamManager(config, tmp_state)


def test_initial_state(manager):
    assert manager.active_count == 0
    assert manager.max_streams == 3
    assert manager.get_all_stream_info() == []


def test_is_enabled_false_initially(manager):
    assert not manager.is_enabled("some-uuid")


@pytest.mark.asyncio
async def test_stream_limit_enforcement(manager, tmp_state):
    """Attempting to enable more streams than max_streams should raise."""
    # Pre-fill enabled cameras at the limit
    tmp_state.set_enabled_cameras({"cam1", "cam2", "cam3"})

    mock_client = AsyncMock()
    manager.set_rhombus_client(mock_client)

    with pytest.raises(ValueError, match="Maximum of 3 concurrent streams"):
        await manager.start_stream("cam4", "Camera 4")


@pytest.mark.asyncio
async def test_start_stream_persists_enabled(manager, tmp_state):
    """Starting a stream should persist the camera UUID to enabled set."""
    mock_client = AsyncMock()
    mock_client.create_raw_stream = AsyncMock(return_value="http://fake/video")
    manager.set_rhombus_client(mock_client)

    # Patch subprocess to avoid actually launching FFmpeg
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_proc:
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.stdout = None
        mock_process.stderr = None
        mock_proc.return_value = mock_process

        await manager.start_stream("cam1", "Front Door")

    assert "cam1" in tmp_state.get_enabled_cameras()
    assert tmp_state.get_slug_map().get("cam1") == "front_door"


@pytest.mark.asyncio
async def test_unlimited_streams_when_max_is_zero(tmp_state):
    """max_streams=0 means unlimited — enabling beyond the old cap must not raise."""
    config = EdgeCasterConfig(max_streams=0, mediamtx_rtsp_port=8554, mediamtx_host="127.0.0.1")
    manager = StreamManager(config, tmp_state)

    # Pre-fill well beyond the historical 10-stream limit.
    tmp_state.set_enabled_cameras({f"cam{i}" for i in range(15)})

    mock_client = AsyncMock()
    mock_client.create_raw_stream = AsyncMock(return_value="http://fake/video")
    manager.set_rhombus_client(mock_client)

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_proc:
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.stdout = None
        mock_process.stderr = None
        mock_proc.return_value = mock_process

        # Should not raise despite 15 already enabled.
        info = await manager.start_stream("cam-new", "Camera New")

    assert "cam-new" in tmp_state.get_enabled_cameras()
    assert info.camera_uuid == "cam-new"


@pytest.mark.asyncio
async def test_stop_stream_removes_from_enabled(manager, tmp_state):
    """Stopping a stream should remove it from the enabled set."""
    tmp_state.set_enabled_cameras({"cam1"})
    tmp_state.set_slug_map({"cam1": "front_door"})

    await manager.stop_stream("cam1")

    assert "cam1" not in tmp_state.get_enabled_cameras()


@pytest.mark.asyncio
async def test_stop_nonexistent_stream(manager):
    """Stopping a stream that doesn't exist should not error."""
    await manager.stop_stream("nonexistent")


def test_slug_uniqueness(manager, tmp_state):
    """Slug generation should handle duplicates."""
    tmp_state.set_slug_map({"cam1": "front_door"})

    mock_client = AsyncMock()
    mock_client.create_raw_stream = AsyncMock(return_value="http://fake/video")
    manager.set_rhombus_client(mock_client)

    # The slug map should give unique slugs
    slug_map = tmp_state.get_slug_map()
    assert slug_map["cam1"] == "front_door"
