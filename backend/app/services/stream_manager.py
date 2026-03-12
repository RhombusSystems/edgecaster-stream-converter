"""Stream manager: orchestrates FFmpeg processes for RTSP rebroadcasting."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from backend.app.config import EdgeCasterConfig
from backend.app.models.stream import StreamInfo, StreamState
from backend.app.services.mediamtx import build_rtsp_playback_url, build_rtsp_publish_url
from backend.app.services.rhombus_api import RhombusClient, RhombusAPIError
from backend.app.services.state_store import StateStore
from backend.app.utils.network import get_local_ip
from backend.app.utils.slugify import slugify

logger = logging.getLogger("edgecaster.stream_manager")

RETRY_DELAY_SECONDS = 5
MAX_RETRY_ATTEMPTS = 10


@dataclass
class ManagedStream:
    """Internal tracking for a running stream."""

    camera_uuid: str
    camera_name: str
    rtsp_slug: str
    lan_video_url: str = ""
    process: asyncio.subprocess.Process | None = None
    state: StreamState = StreamState.STOPPED
    error_message: str = ""
    retry_count: int = 0
    monitor_task: asyncio.Task | None = field(default=None, repr=False)


class StreamManager:
    """Manages FFmpeg subprocesses that pull Rhombus SRS and publish to MediaMTX."""

    def __init__(
        self,
        config: EdgeCasterConfig,
        state_store: StateStore,
    ) -> None:
        self._config = config
        self._state_store = state_store
        self._streams: dict[str, ManagedStream] = {}  # camera_uuid -> ManagedStream
        self._rhombus_client: RhombusClient | None = None
        self._shutting_down = False

    def set_rhombus_client(self, client: RhombusClient) -> None:
        self._rhombus_client = client

    @property
    def active_count(self) -> int:
        return sum(
            1 for s in self._streams.values() if s.state in (StreamState.RUNNING, StreamState.STARTING, StreamState.RESTARTING)
        )

    @property
    def max_streams(self) -> int:
        return self._config.max_streams

    def get_stream_info(self, camera_uuid: str) -> StreamInfo | None:
        stream = self._streams.get(camera_uuid)
        if not stream:
            return None
        return self._to_stream_info(stream)

    def get_all_stream_info(self) -> list[StreamInfo]:
        return [self._to_stream_info(s) for s in self._streams.values()]

    def is_enabled(self, camera_uuid: str) -> bool:
        return camera_uuid in self._state_store.get_enabled_cameras()

    async def start_stream(self, camera_uuid: str, camera_name: str) -> StreamInfo:
        """Enable and start streaming for a camera."""
        if self._shutting_down:
            raise RuntimeError("Stream manager is shutting down")

        # Check stream limit
        enabled = self._state_store.get_enabled_cameras()
        if camera_uuid not in enabled and len(enabled) >= self._config.max_streams:
            raise ValueError(
                f"Maximum of {self._config.max_streams} concurrent streams reached. "
                "Disable another stream first."
            )

        # Generate deterministic slug
        slug_map = self._state_store.get_slug_map()
        slug = slug_map.get(camera_uuid)
        if not slug:
            slug = slugify(camera_name)
            # Ensure uniqueness
            existing_slugs = set(slug_map.values())
            base_slug = slug
            counter = 1
            while slug in existing_slugs:
                slug = f"{base_slug}_{counter}"
                counter += 1
            slug_map[camera_uuid] = slug
            self._state_store.set_slug_map(slug_map)

        # Persist enabled state
        enabled.add(camera_uuid)
        self._state_store.set_enabled_cameras(enabled)

        # Create or update managed stream
        stream = self._streams.get(camera_uuid)
        if stream is None:
            stream = ManagedStream(
                camera_uuid=camera_uuid,
                camera_name=camera_name,
                rtsp_slug=slug,
            )
            self._streams[camera_uuid] = stream

        stream.state = StreamState.STARTING
        stream.error_message = ""
        stream.retry_count = 0

        # Launch the stream pipeline
        await self._launch_stream(stream)
        return self._to_stream_info(stream)

    async def stop_stream(self, camera_uuid: str) -> None:
        """Disable and stop streaming for a camera."""
        # Remove from enabled set
        enabled = self._state_store.get_enabled_cameras()
        enabled.discard(camera_uuid)
        self._state_store.set_enabled_cameras(enabled)

        stream = self._streams.get(camera_uuid)
        if stream is None:
            return

        await self._kill_stream(stream)
        stream.state = StreamState.STOPPED
        stream.error_message = ""

        # Cancel monitor task
        if stream.monitor_task and not stream.monitor_task.done():
            stream.monitor_task.cancel()
            try:
                await stream.monitor_task
            except asyncio.CancelledError:
                pass

        # Clean up Rhombus raw stream
        if self._rhombus_client:
            try:
                await self._rhombus_client.delete_raw_stream(camera_uuid)
            except Exception as e:
                logger.warning("Failed to clean up raw stream for %s: %s", camera_uuid, e)

        del self._streams[camera_uuid]

    async def restore_streams(self, camera_map: dict[str, str]) -> None:
        """Restore previously enabled streams after restart.

        Args:
            camera_map: dict of camera_uuid -> camera_name for known cameras.
        """
        enabled = self._state_store.get_enabled_cameras()
        if not enabled:
            logger.info("No streams to restore")
            return

        logger.info("Restoring %d streams", len(enabled))
        for uuid in enabled:
            name = camera_map.get(uuid, "Unknown")
            try:
                await self.start_stream(uuid, name)
                logger.info("Restored stream for %s (%s)", name, uuid)
            except Exception as e:
                logger.error("Failed to restore stream for %s: %s", uuid, e)

    async def shutdown(self) -> None:
        """Gracefully stop all streams."""
        self._shutting_down = True
        logger.info("Shutting down stream manager, stopping %d streams", len(self._streams))

        tasks = []
        for stream in list(self._streams.values()):
            if stream.monitor_task and not stream.monitor_task.done():
                stream.monitor_task.cancel()
            tasks.append(self._kill_stream(stream))

        await asyncio.gather(*tasks, return_exceptions=True)
        self._streams.clear()
        logger.info("Stream manager shutdown complete")

    async def _launch_stream(self, stream: ManagedStream) -> None:
        """Request SRS URL from Rhombus and launch FFmpeg."""
        if not self._rhombus_client:
            stream.state = StreamState.FAILED
            stream.error_message = "Rhombus API client not configured"
            return

        try:
            # Request a new Secure Raw Stream URL
            stream_name = f"edgecaster_{stream.rtsp_slug}"
            lan_video_url = await self._rhombus_client.create_raw_stream(
                stream.camera_uuid, stream_name
            )
            stream.lan_video_url = lan_video_url

            # Build FFmpeg command
            publish_url = build_rtsp_publish_url(
                self._config.mediamtx_host,
                self._config.mediamtx_rtsp_port,
                stream.rtsp_slug,
            )

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", self._config.ffmpeg_loglevel,
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", lan_video_url,
                "-c", "copy",
                "-f", "rtsp",
                "-rtsp_transport", "tcp",
                publish_url,
            ]

            logger.info("Starting FFmpeg for %s: %s -> %s", stream.camera_name, lan_video_url, publish_url)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stream.process = process
            stream.state = StreamState.RUNNING
            stream.error_message = ""

            # Start monitoring task
            stream.monitor_task = asyncio.create_task(
                self._monitor_stream(stream),
                name=f"monitor-{stream.camera_uuid}",
            )

        except RhombusAPIError as e:
            logger.error("Failed to create raw stream for %s: %s", stream.camera_uuid, e)
            stream.state = StreamState.FAILED
            stream.error_message = str(e)
        except FileNotFoundError:
            logger.error("FFmpeg not found. Ensure FFmpeg is installed.")
            stream.state = StreamState.FAILED
            stream.error_message = "FFmpeg not found on system"
        except Exception as e:
            logger.error("Unexpected error starting stream for %s: %s", stream.camera_uuid, e)
            stream.state = StreamState.FAILED
            stream.error_message = str(e)

    async def _monitor_stream(self, stream: ManagedStream) -> None:
        """Monitor an FFmpeg process and restart on failure."""
        while not self._shutting_down and stream.camera_uuid in self._state_store.get_enabled_cameras():
            if stream.process is None:
                break

            # Wait for process to exit
            return_code = await stream.process.wait()

            if self._shutting_down:
                break

            if return_code == 0:
                logger.info("FFmpeg exited normally for %s", stream.camera_name)
                break

            # Process failed
            stream.retry_count += 1
            stderr_output = ""
            if stream.process.stderr:
                try:
                    stderr_bytes = await stream.process.stderr.read()
                    stderr_output = stderr_bytes.decode(errors="replace")[-500:]
                except Exception:
                    pass

            logger.warning(
                "FFmpeg exited with code %d for %s (attempt %d/%d): %s",
                return_code,
                stream.camera_name,
                stream.retry_count,
                MAX_RETRY_ATTEMPTS,
                stderr_output,
            )

            if stream.retry_count >= MAX_RETRY_ATTEMPTS:
                stream.state = StreamState.FAILED
                stream.error_message = f"Max retries exceeded (last exit code: {return_code})"
                logger.error("Giving up on stream for %s after %d attempts", stream.camera_name, MAX_RETRY_ATTEMPTS)
                break

            # Retry
            stream.state = StreamState.RESTARTING
            stream.error_message = f"Restarting (attempt {stream.retry_count})"
            logger.info("Retrying stream for %s in %ds", stream.camera_name, RETRY_DELAY_SECONDS)
            await asyncio.sleep(RETRY_DELAY_SECONDS)

            if self._shutting_down:
                break

            # Re-create raw stream (token may have expired)
            await self._launch_stream(stream)
            return  # _launch_stream creates a new monitor task

    async def _kill_stream(self, stream: ManagedStream) -> None:
        """Terminate an FFmpeg process."""
        if stream.process is None:
            return

        try:
            stream.process.terminate()
            try:
                await asyncio.wait_for(stream.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("FFmpeg did not exit gracefully for %s, killing", stream.camera_name)
                stream.process.kill()
                await stream.process.wait()
        except ProcessLookupError:
            pass  # Already dead
        finally:
            stream.process = None

    def _to_stream_info(self, stream: ManagedStream) -> StreamInfo:
        local_ip = get_local_ip()
        rtsp_url = build_rtsp_playback_url(local_ip, self._config.mediamtx_rtsp_port, stream.rtsp_slug)
        return StreamInfo(
            camera_uuid=stream.camera_uuid,
            camera_name=stream.camera_name,
            rtsp_path=stream.rtsp_slug,
            rtsp_url=rtsp_url,
            state=stream.state,
            error_message=stream.error_message,
            lan_video_url=stream.lan_video_url,
        )
