"""Read and live-tail EdgeCaster log files for the dashboard Logs view."""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path

# Friendly source name -> log filename (whitelist; never accept arbitrary paths).
LOG_SOURCES: dict[str, str] = {
    "application": "app.log",
    "streams": "stream_manager.log",
    "rhombus": "rhombus_api.log",
}

_POLL_INTERVAL = 1.0
_MAX_LINE = 8192


def available_sources(log_dir: Path) -> list[dict]:
    """Return sources with whether their file currently exists."""
    out = []
    for name, fname in LOG_SOURCES.items():
        out.append({"name": name, "exists": (log_dir / fname).exists()})
    return out


def _resolve(log_dir: Path, source: str) -> Path | None:
    fname = LOG_SOURCES.get(source)
    if not fname:
        return None
    return log_dir / fname


def read_tail(log_dir: Path, source: str, lines: int = 200) -> list[str]:
    """Return the last ``lines`` lines of a log source (empty if missing)."""
    path = _resolve(log_dir, source)
    if path is None or not path.exists():
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in deque(f, maxlen=lines)]
    except Exception:  # noqa: BLE001
        return []


async def tail_stream(log_dir: Path, source: str):
    """Async generator yielding new log lines as they are appended.

    Starts from the current end of file, then follows. Handles log rotation
    (file truncated/replaced) by reopening from the top.
    """
    path = _resolve(log_dir, source)
    if path is None:
        return

    pos = 0
    if path.exists():
        pos = path.stat().st_size  # start at end — only stream new lines
    buf = ""

    while True:
        try:
            if not path.exists():
                await asyncio.sleep(_POLL_INTERVAL)
                continue
            size = path.stat().st_size
            if size < pos:  # rotated/truncated -> restart
                pos = 0
                buf = ""
            if size > pos:
                with open(path, encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                buf += chunk
                *complete, buf = buf.split("\n")
                if len(buf) > _MAX_LINE:  # avoid unbounded partial line
                    buf = buf[-_MAX_LINE:]
                for line in complete:
                    yield line
        except Exception:  # noqa: BLE001 - never crash the SSE loop
            pass
        await asyncio.sleep(_POLL_INTERVAL)
