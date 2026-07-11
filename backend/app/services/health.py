"""System health monitoring — CPU/memory plus Raspberry Pi strain metrics."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from backend.app.models.settings import Alert, SystemStatus
from backend.app.utils.network import get_hostname, get_local_ip

logger = logging.getLogger("edgecaster.health")

_boot_time = time.time()

_THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")
_VCGENCMD = shutil.which("vcgencmd") or "/usr/bin/vcgencmd"


def read_temperature_c() -> float:
    """Read SoC temperature in Celsius from sysfs (world-readable). 0 if unavailable."""
    try:
        raw = _THERMAL_ZONE.read_text().strip()
        return round(int(raw) / 1000.0, 1)
    except Exception:  # noqa: BLE001 - non-Pi / missing sysfs
        return 0.0


def parse_throttled(hex_value: str) -> dict:
    """Decode a ``vcgencmd get_throttled`` bitmask.

    See https://www.raspberrypi.com/documentation/computers/os.html#get_throttled
    """
    try:
        bits = int(hex_value, 16)
    except (ValueError, TypeError):
        return {}
    return {
        "under_voltage_now": bool(bits & (1 << 0)),
        "freq_capped_now": bool(bits & (1 << 1)),
        "throttled_now": bool(bits & (1 << 2)),
        "under_voltage_occurred": bool(bits & (1 << 16)),
        "throttled_occurred": bool(bits & (1 << 18)),
    }


def _throttle_status(flags: dict) -> str:
    if not flags:
        return "unknown"
    if flags.get("under_voltage_now"):
        return "under_voltage"
    if flags.get("throttled_now") or flags.get("freq_capped_now"):
        return "throttled"
    return "ok"


def _parse_vcgencmd_output(out: str) -> dict:
    # Output looks like "throttled=0x50000"
    _, _, value = out.strip().partition("=")
    return parse_throttled(value)


def read_throttled_sync() -> dict:
    """Blocking read of the throttle bitmask via vcgencmd. Empty dict if unavailable."""
    try:
        out = subprocess.run(  # noqa: S603
            [_VCGENCMD, "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0:
            return _parse_vcgencmd_output(out.stdout)
    except Exception as e:  # noqa: BLE001 - vcgencmd missing / no perms
        logger.debug("vcgencmd get_throttled failed: %s", e)
    return {}


async def read_throttled_async() -> dict:
    """Non-blocking read of the throttle bitmask via vcgencmd."""
    try:
        proc = await asyncio.create_subprocess_exec(
            _VCGENCMD,
            "get_throttled",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2)
        if proc.returncode == 0:
            return _parse_vcgencmd_output(stdout.decode(errors="replace"))
    except Exception as e:  # noqa: BLE001
        logger.debug("vcgencmd (async) failed: %s", e)
    return {}


def _load_avg() -> tuple[float, float, float]:
    try:
        return os.getloadavg()
    except (OSError, AttributeError):
        return (0.0, 0.0, 0.0)


def _cpu_freq_mhz() -> float:
    try:
        freq = psutil.cpu_freq()
        return round(freq.current, 0) if freq else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


class MetricsCollector:
    """Collects system metrics and caches the latest snapshot for SSE + REST.

    ``psutil.cpu_percent(interval=None)`` is primed once at construction so all
    later calls are non-blocking (they report usage since the previous call).
    """

    def __init__(self) -> None:
        psutil.cpu_percent(interval=None)  # prime the non-blocking sampler
        self.latest: SystemStatus | None = None

    def _build(
        self,
        *,
        total_cameras: int,
        active_streams: int,
        max_streams: int,
        throttle_flags: dict,
        alerts: list[Alert] | None,
    ) -> SystemStatus:
        la1, la5, la15 = _load_avg()
        status = SystemStatus(
            hostname=get_hostname(),
            local_ip=get_local_ip(),
            uptime_seconds=round(time.time() - _boot_time, 1),
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=psutil.virtual_memory().percent,
            total_cameras=total_cameras,
            active_streams=active_streams,
            max_streams=max_streams,
            temperature_c=read_temperature_c(),
            throttle_status=_throttle_status(throttle_flags),
            under_voltage_now=throttle_flags.get("under_voltage_now", False),
            under_voltage_occurred=throttle_flags.get("under_voltage_occurred", False),
            throttled_now=throttle_flags.get("throttled_now", False),
            throttled_occurred=throttle_flags.get("throttled_occurred", False),
            freq_capped_now=throttle_flags.get("freq_capped_now", False),
            load_avg_1m=round(la1, 2),
            load_avg_5m=round(la5, 2),
            load_avg_15m=round(la15, 2),
            cpu_count=psutil.cpu_count() or os.cpu_count() or 0,
            cpu_freq_mhz=_cpu_freq_mhz(),
            alerts=alerts or [],
        )
        return status

    async def sample(
        self,
        *,
        total_cameras: int = 0,
        active_streams: int = 0,
        max_streams: int = 0,
        alerts: list[Alert] | None = None,
    ) -> SystemStatus:
        """Async sample (non-blocking vcgencmd); updates and returns ``latest``."""
        throttle_flags = await read_throttled_async()
        status = self._build(
            total_cameras=total_cameras,
            active_streams=active_streams,
            max_streams=max_streams,
            throttle_flags=throttle_flags,
            alerts=alerts,
        )
        self.latest = status
        return status

    def sample_sync(
        self,
        *,
        total_cameras: int = 0,
        active_streams: int = 0,
        max_streams: int = 0,
    ) -> SystemStatus:
        """Blocking sample for the REST fallback endpoint."""
        status = self._build(
            total_cameras=total_cameras,
            active_streams=active_streams,
            max_streams=max_streams,
            throttle_flags=read_throttled_sync(),
            alerts=None,
        )
        self.latest = status
        return status


# Module-level singleton used by the REST fallback endpoint.
_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    return _collector


def get_system_status(
    total_cameras: int = 0, active_streams: int = 0, max_streams: int = 0
) -> SystemStatus:
    """Collect current system health metrics (blocking; REST fallback)."""
    return _collector.sample_sync(
        total_cameras=total_cameras,
        active_streams=active_streams,
        max_streams=max_streams,
    )
