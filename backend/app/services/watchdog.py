"""Systemd watchdog integration via raw sd_notify socket."""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger("edgecaster")

WATCHDOG_INTERVAL = 10  # seconds between pings (well within 30s WatchdogSec)


def _sd_notify(state: str) -> None:
    """Send a notification to systemd via NOTIFY_SOCKET."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return

    if addr.startswith("@"):
        addr = "\0" + addr[1:]

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(addr)
        sock.sendall(state.encode())
        sock.close()
    except OSError:
        pass  # Not running under systemd — silently ignore


def notify_ready() -> None:
    """Tell systemd the service is ready."""
    _sd_notify("READY=1")
    logger.debug("Sent READY=1 to systemd")


def notify_stopping() -> None:
    """Tell systemd the service is stopping."""
    _sd_notify("STOPPING=1")
    logger.debug("Sent STOPPING=1 to systemd")


async def watchdog_loop() -> None:
    """Periodically ping the systemd watchdog to prove liveness."""
    while True:
        _sd_notify("WATCHDOG=1")
        await asyncio.sleep(WATCHDOG_INTERVAL)
