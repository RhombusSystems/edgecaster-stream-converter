"""Stream manager: orchestrates FFmpeg processes for RTSP rebroadcasting.

Design goals:
- Sub-second latency: FFmpeg stream-copy with all buffering minimized (see the
  command in ``_launch_stream``). Latency is won by removing buffering at every
  hop, not by transcoding (``-c copy`` cannot drop or re-time frames).
- 24/7 self-healing: three always-running tasks per stream (stdout progress
  drain, stderr drain, exit monitor) plus a stall watchdog that detects a frozen
  feed even while the FFmpeg process is still alive. Every recovery trigger
  funnels through one generation-guarded ``_recover`` so there is never a
  double relaunch.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

from backend.app.config import EdgeCasterConfig
from backend.app.models.stream import StreamInfo, StreamState
from backend.app.services.alerts import AlertManager
from backend.app.services.mediamtx import (
    PathStats,
    build_rtsp_playback_url,
    build_rtsp_publish_url,
)
from backend.app.services.posthog_service import capture_event, capture_exception
from backend.app.services.rhombus_api import RhombusAPIError, RhombusClient
from backend.app.services.state_store import StateStore
from backend.app.utils.network import get_local_ip
from backend.app.utils.slugify import slugify

logger = logging.getLogger("edgecaster.stream_manager")

RETRY_DELAY_SECONDS = 5
MAX_RETRY_ATTEMPTS = 10
RECOVERY_BACKOFF_SECONDS = 300  # 5-minute backoff after max retries exhausted
WATCHDOG_INTERVAL = 2  # seconds between stall/health sweeps
STARTUP_GRACE_SECONDS = 4  # don't evaluate stalls until the stream has negotiated
HEALTHY_RESET_SECONDS = 60  # sustained healthy runtime before resetting counters

# Reasons that use the hard-failure retry ladder vs. the light stall backoff.
_EXIT_REASONS = {"process_exit", "dead_process"}


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
    stall_count: int = 0

    # Recovery coordination
    recovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    restart_generation: int = 0

    # Liveness (monotonic clock)
    started_ts: float = 0.0
    last_progress_ts: float = 0.0
    last_out_time: int = -1
    last_total_size: int = -1

    # Tasks
    monitor_task: asyncio.Task | None = field(default=None, repr=False)
    progress_task: asyncio.Task | None = field(default=None, repr=False)
    stderr_task: asyncio.Task | None = field(default=None, repr=False)
    stderr_tail: deque = field(default_factory=lambda: deque(maxlen=50), repr=False)

    # MediaMTX-derived throughput/reader stats
    bytes_received: int = 0
    readers: int = 0
    throughput_kbps: float = 0.0
    last_bytes_received: int = -1
    last_bytes_ts: float = 0.0
    last_bytes_change_ts: float = 0.0


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
        self._alert_manager: AlertManager | None = None
        self._shutting_down = False

    def set_rhombus_client(self, client: RhombusClient) -> None:
        self._rhombus_client = client

    def set_alert_manager(self, manager: AlertManager) -> None:
        self._alert_manager = manager

    @property
    def active_count(self) -> int:
        return sum(
            1
            for s in self._streams.values()
            if s.state in (StreamState.RUNNING, StreamState.STARTING, StreamState.RESTARTING)
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

        # Optional hard safety ceiling (0 = unlimited).
        limit = self._config.max_streams
        enabled = self._state_store.get_enabled_cameras()
        if limit > 0 and camera_uuid not in enabled and len(enabled) >= limit:
            raise ValueError(
                f"Maximum of {limit} concurrent streams reached. "
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
        stream.stall_count = 0

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

        # Bump generation so any in-flight monitor/watchdog trigger is ignored.
        stream.restart_generation += 1
        await self._kill_stream(stream)
        self._cancel_tasks(stream)
        stream.state = StreamState.STOPPED
        stream.error_message = ""

        if self._alert_manager:
            await self._alert_manager.clear_alert(f"stream_down:{camera_uuid}")

        # Clean up Rhombus raw stream
        if self._rhombus_client:
            try:
                await self._rhombus_client.delete_raw_stream(camera_uuid)
            except Exception as e:
                logger.warning("Failed to clean up raw stream for %s: %s", camera_uuid, e)

        del self._streams[camera_uuid]

    async def restore_streams(self, camera_map: dict[str, str]) -> None:
        """Restore previously enabled streams after restart."""
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
            self._cancel_tasks(stream)
            tasks.append(self._kill_stream(stream))

        await asyncio.gather(*tasks, return_exceptions=True)
        self._streams.clear()
        logger.info("Stream manager shutdown complete")

    async def _launch_stream(self, stream: ManagedStream) -> None:
        """Request a fresh SRS URL from Rhombus and launch FFmpeg + monitor tasks."""
        if not self._rhombus_client:
            stream.state = StreamState.FAILED
            stream.error_message = "Rhombus API client not configured"
            return

        try:
            # Request a fresh Secure Raw Stream URL (tokens expire, so always refetch).
            stream_name = f"edgecaster_{stream.rtsp_slug}"
            lan_video_url = await self._rhombus_client.create_raw_stream(
                stream.camera_uuid, stream_name
            )
            stream.lan_video_url = lan_video_url

            publish_url = build_rtsp_publish_url(
                self._config.mediamtx_host,
                self._config.mediamtx_rtsp_port,
                stream.rtsp_slug,
            )

            cmd = self._build_ffmpeg_cmd(lan_video_url, publish_url)

            logger.info(
                "Starting FFmpeg for %s: %s -> %s",
                stream.camera_name,
                lan_video_url,
                publish_url,
            )

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stream.process = process
            stream.state = StreamState.RUNNING
            stream.error_message = ""

            # Reset liveness clocks for the new process.
            now = time.monotonic()
            stream.started_ts = now
            stream.last_progress_ts = now
            stream.last_out_time = -1
            stream.last_total_size = -1
            stream.last_bytes_received = -1
            stream.last_bytes_change_ts = now

            capture_event("stream_started", {
                "camera_uuid": stream.camera_uuid,
                "camera_name": stream.camera_name,
                "rtsp_slug": stream.rtsp_slug,
            })

            # Spawn the three always-running tasks, tagged with this generation.
            generation = stream.restart_generation
            self._cancel_tasks(stream)
            stream.stderr_tail.clear()
            stream.monitor_task = asyncio.create_task(
                self._monitor_stream(stream, generation),
                name=f"monitor-{stream.camera_uuid}",
            )
            stream.progress_task = asyncio.create_task(
                self._drain_progress(stream, process),
                name=f"progress-{stream.camera_uuid}",
            )
            stream.stderr_task = asyncio.create_task(
                self._drain_stderr(stream, process),
                name=f"stderr-{stream.camera_uuid}",
            )

        except RhombusAPIError as e:
            logger.error("Failed to create raw stream for %s: %s", stream.camera_uuid, e)
            stream.state = StreamState.FAILED
            stream.error_message = str(e)
            capture_exception(e, {"camera_uuid": stream.camera_uuid, "phase": "create_raw_stream"})
            capture_event("stream_failed", {
                "camera_uuid": stream.camera_uuid,
                "camera_name": stream.camera_name,
                "error": str(e),
                "reason": "rhombus_api_error",
            })
        except FileNotFoundError as e:
            logger.error("FFmpeg not found. Ensure FFmpeg is installed.")
            stream.state = StreamState.FAILED
            stream.error_message = "FFmpeg not found on system"
            capture_exception(e, {"camera_uuid": stream.camera_uuid, "phase": "ffmpeg_launch"})
            capture_event("stream_failed", {
                "camera_uuid": stream.camera_uuid,
                "reason": "ffmpeg_not_found",
            })
        except Exception as e:
            logger.error("Unexpected error starting stream for %s: %s", stream.camera_uuid, e)
            stream.state = StreamState.FAILED
            stream.error_message = str(e)
            capture_exception(e, {"camera_uuid": stream.camera_uuid, "phase": "stream_launch"})

    def _build_ffmpeg_cmd(self, lan_video_url: str, publish_url: str) -> list[str]:
        """Assemble the low-latency stream-copy FFmpeg command."""
        c = self._config
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", c.ffmpeg_loglevel,
            # --- input: minimize ingest buffering & analysis time ---
            "-fflags", "nobuffer+flush_packets",
            "-flags", "low_delay",
            "-avioflags", "direct",
            "-probesize", str(c.ffmpeg_probesize),
            "-analyzeduration", str(c.ffmpeg_analyzeduration),
            "-rw_timeout", str(c.ffmpeg_rw_timeout),
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-reconnect_delay_max", "2",
            "-i", lan_video_url,
            # --- output: stream copy, no mux buffering ---
            "-c", "copy",
            "-muxdelay", "0",
            "-muxpreload", "0",
            "-max_delay", "0",
            "-flush_packets", "1",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            # machine-readable liveness (also keeps stdout drained)
            "-progress", "pipe:1",
            "-stats_period", "1",
            publish_url,
        ]

    async def _drain_progress(
        self, stream: ManagedStream, process: asyncio.subprocess.Process
    ) -> None:
        """Continuously read FFmpeg -progress output; stamp liveness on advance.

        Draining stdout also prevents the OS pipe from filling and blocking FFmpeg.
        """
        if process.stdout is None:
            return
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break  # EOF — process exited
                key, sep, value = line.decode(errors="replace").strip().partition("=")
                if not sep:
                    continue
                if key == "out_time_us":
                    try:
                        v = int(value)
                    except ValueError:
                        continue
                    if v > stream.last_out_time:
                        stream.last_out_time = v
                        stream.last_progress_ts = time.monotonic()
                elif key == "total_size":
                    try:
                        v = int(value)
                    except ValueError:
                        continue
                    if v > stream.last_total_size:
                        stream.last_total_size = v
                        stream.last_progress_ts = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.debug("progress drain ended for %s: %s", stream.camera_name, e)

    async def _drain_stderr(
        self, stream: ManagedStream, process: asyncio.subprocess.Process
    ) -> None:
        """Continuously read FFmpeg stderr into a bounded tail for diagnostics."""
        if process.stderr is None:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                stream.stderr_tail.append(line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.debug("stderr drain ended for %s: %s", stream.camera_name, e)

    async def _monitor_stream(self, stream: ManagedStream, generation: int) -> None:
        """Await FFmpeg exit; funnel unexpected exits into unified recovery."""
        process = stream.process
        if process is None:
            return

        return_code = await process.wait()

        if self._shutting_down:
            return
        # A newer generation means recovery/stop already took over — exit quietly.
        if generation != stream.restart_generation:
            return
        if return_code == 0:
            logger.info("FFmpeg exited normally for %s", stream.camera_name)
            return

        await self._recover(stream, generation, "process_exit", exit_code=return_code)

    def health_check_loop(self):
        """Backwards-compatible name; runs the stall + dead-process watchdog."""
        return self._watchdog_loop()

    async def _watchdog_loop(self) -> None:
        """Every WATCHDOG_INTERVAL: detect stalled feeds and dead processes."""
        while not self._shutting_down:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            if self._shutting_down:
                break

            now = time.monotonic()
            threshold = max(self._config.stall_threshold_seconds, 2)

            for stream in list(self._streams.values()):
                if stream.state != StreamState.RUNNING:
                    continue

                gen = stream.restart_generation

                # Dead process the exit monitor somehow missed.
                if stream.process is None or stream.process.returncode is not None:
                    logger.warning(
                        "Watchdog: dead process for %s, recovering", stream.camera_name
                    )
                    await self._recover(stream, gen, "dead_process")
                    continue

                # Startup grace so slow-negotiating streams aren't killed.
                if now - stream.started_ts < STARTUP_GRACE_SECONDS:
                    continue

                progress_stalled = (now - stream.last_progress_ts) > threshold
                # Secondary check via MediaMTX bytesReceived (only if API is live and
                # the path has received data before — avoids false positives).
                bytes_stalled = (
                    stream.last_bytes_received > 0
                    and (now - stream.last_bytes_change_ts) > threshold
                )

                if progress_stalled or bytes_stalled:
                    reason = "progress_stall" if progress_stalled else "bytes_stall"
                    await self._recover(stream, gen, reason)
                    continue

                # Healthy for a sustained period → reset counters and clear any
                # standing stream-down alert.
                if (
                    now - stream.started_ts > HEALTHY_RESET_SECONDS
                    and (stream.retry_count or stream.stall_count)
                ):
                    stream.retry_count = 0
                    stream.stall_count = 0
                    if self._alert_manager:
                        await self._alert_manager.clear_alert(
                            f"stream_down:{stream.camera_uuid}"
                        )

    async def _recover(
        self,
        stream: ManagedStream,
        observed_generation: int,
        reason: str,
        exit_code: int | None = None,
    ) -> None:
        """Single guarded recovery entry point for every failure trigger.

        The ``observed_generation`` guard ensures that if two triggers fire for
        the same failure, only the first performs a relaunch; the second sees a
        newer generation and returns — no double relaunch.
        """
        async with stream.recovery_lock:
            if self._shutting_down:
                return
            if stream.camera_uuid not in self._state_store.get_enabled_cameras():
                return
            # Already handled since this trigger observed the failure.
            if observed_generation != stream.restart_generation:
                return

            # Claim this recovery: bump generation so stale triggers are ignored.
            stream.restart_generation += 1
            stream.state = StreamState.RESTARTING

            fast = reason not in _EXIT_REASONS
            await self._kill_stream(stream, fast=fast)
            self._cancel_tasks(stream)

            if reason in _EXIT_REASONS:
                stream.retry_count += 1
                tail = " | ".join(list(stream.stderr_tail)[-6:])
                logger.warning(
                    "FFmpeg failure (%s, code=%s) for %s (attempt %d/%d): %s",
                    reason,
                    exit_code,
                    stream.camera_name,
                    stream.retry_count,
                    MAX_RETRY_ATTEMPTS,
                    tail,
                )
                if stream.retry_count >= MAX_RETRY_ATTEMPTS:
                    stream.state = StreamState.FAILED
                    stream.error_message = (
                        f"Retries exhausted, backing off {RECOVERY_BACKOFF_SECONDS}s"
                    )
                    logger.error(
                        "Max retries for %s exhausted, backing off %ds",
                        stream.camera_name,
                        RECOVERY_BACKOFF_SECONDS,
                    )
                    capture_event("stream_retries_exhausted", {
                        "camera_uuid": stream.camera_uuid,
                        "camera_name": stream.camera_name,
                        "retry_count": stream.retry_count,
                        "last_exit_code": exit_code,
                        "backoff_seconds": RECOVERY_BACKOFF_SECONDS,
                    })
                    await self._alert_stream_down(stream, exit_code)
                    await asyncio.sleep(RECOVERY_BACKOFF_SECONDS)
                    if self._shutting_down or not self.is_enabled(stream.camera_uuid):
                        return
                    stream.retry_count = 0
                    stream.state = StreamState.RESTARTING
                else:
                    stream.error_message = f"Restarting (attempt {stream.retry_count})"
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                stream.stall_count += 1
                logger.warning(
                    "Stream %s %s (stall #%d) — killing and refetching a fresh URL",
                    stream.camera_name,
                    reason,
                    stream.stall_count,
                )
                stream.error_message = f"Recovering from stall (#{stream.stall_count})"
                delay = self._stall_backoff(stream.stall_count)
                if delay:
                    await asyncio.sleep(delay)

            if self._shutting_down or not self.is_enabled(stream.camera_uuid):
                return

            await self._launch_stream(stream)

    @staticmethod
    def _stall_backoff(stall_count: int) -> float:
        """Light backoff for repeated stalls to prevent thrashing."""
        if stall_count <= 3:
            return 0.0
        return min(2.0 * (stall_count - 3), 30.0)

    async def _alert_stream_down(self, stream: ManagedStream, exit_code: int | None) -> None:
        if not self._alert_manager:
            return
        await self._alert_manager.raise_alert(
            f"stream_down:{stream.camera_uuid}",
            "critical",
            f"Stream down: {stream.camera_name}",
            f"Could not keep '{stream.camera_name}' streaming after "
            f"{MAX_RETRY_ATTEMPTS} attempts (last exit code {exit_code}).",
            {"camera_uuid": stream.camera_uuid, "rtsp_slug": stream.rtsp_slug},
        )

    def apply_path_stats(self, path_stats: dict[str, PathStats]) -> None:
        """Update per-stream throughput/reader stats from the MediaMTX API."""
        now = time.monotonic()
        for stream in self._streams.values():
            st = path_stats.get(stream.rtsp_slug)
            if st is None:
                continue
            stream.readers = st.readers
            if stream.last_bytes_received >= 0 and st.bytes_received >= stream.last_bytes_received:
                delta_bytes = st.bytes_received - stream.last_bytes_received
                dt = now - stream.last_bytes_ts
                if dt > 0:
                    stream.throughput_kbps = round((delta_bytes * 8 / 1000.0) / dt, 1)
                if delta_bytes > 0:
                    stream.last_bytes_change_ts = now
            else:
                # First sample (or counter reset on relaunch).
                stream.last_bytes_change_ts = now
            stream.bytes_received = st.bytes_received
            stream.last_bytes_received = st.bytes_received
            stream.last_bytes_ts = now

    def _cancel_tasks(self, stream: ManagedStream) -> None:
        """Cancel the per-stream drain/monitor tasks (not awaited).

        Never cancels the currently-running task — ``_recover`` is often invoked
        from within the stream's own monitor task, and cancelling self would
        abort the in-progress recovery.
        """
        current = asyncio.current_task()
        for attr in ("progress_task", "stderr_task", "monitor_task"):
            task = getattr(stream, attr)
            if task is current:
                continue
            if task and not task.done():
                task.cancel()
            setattr(stream, attr, None)

    async def _kill_stream(self, stream: ManagedStream, fast: bool = False) -> None:
        """Terminate an FFmpeg process. ``fast`` uses a short grace for stall recovery."""
        if stream.process is None:
            return

        grace = 0.5 if fast else 5.0
        try:
            stream.process.terminate()
            try:
                await asyncio.wait_for(stream.process.wait(), timeout=grace)
            except TimeoutError:
                logger.warning(
                    "FFmpeg did not exit in %ss for %s, killing", grace, stream.camera_name
                )
                stream.process.kill()
                await stream.process.wait()
        except ProcessLookupError:
            pass  # Already dead
        finally:
            stream.process = None

    def _to_stream_info(self, stream: ManagedStream) -> StreamInfo:
        local_ip = get_local_ip()
        rtsp_url = build_rtsp_playback_url(
            local_ip, self._config.mediamtx_rtsp_port, stream.rtsp_slug
        )
        return StreamInfo(
            camera_uuid=stream.camera_uuid,
            camera_name=stream.camera_name,
            rtsp_path=stream.rtsp_slug,
            rtsp_url=rtsp_url,
            state=stream.state,
            error_message=stream.error_message,
            lan_video_url=stream.lan_video_url,
            throughput_kbps=stream.throughput_kbps,
            readers=stream.readers,
        )
