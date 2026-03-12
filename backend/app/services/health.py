"""System health monitoring."""

from __future__ import annotations

import time

import psutil

from backend.app.models.settings import SystemStatus
from backend.app.utils.network import get_hostname, get_local_ip

_boot_time = time.time()


def get_system_status(
    total_cameras: int = 0, active_streams: int = 0, max_streams: int = 10
) -> SystemStatus:
    """Collect current system health metrics."""
    return SystemStatus(
        hostname=get_hostname(),
        local_ip=get_local_ip(),
        uptime_seconds=round(time.time() - _boot_time, 1),
        cpu_percent=psutil.cpu_percent(interval=0.5),
        memory_percent=psutil.virtual_memory().percent,
        total_cameras=total_cameras,
        active_streams=active_streams,
        max_streams=max_streams,
    )
