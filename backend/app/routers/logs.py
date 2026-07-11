"""Live log viewing routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.dependencies import get_config
from backend.app.services.logs import (
    LOG_SOURCES,
    available_sources,
    read_tail,
    tail_stream,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/sources")
async def log_sources() -> dict:
    """List available log sources and whether each currently has a file."""
    return {"sources": available_sources(get_config().log_dir)}


@router.get("")
async def get_logs(
    source: str = Query("streams"),
    lines: int = Query(200, ge=1, le=2000),
) -> dict:
    """Return the most recent lines of a log source (snapshot)."""
    if source not in LOG_SOURCES:
        source = "streams"
    return {"source": source, "lines": read_tail(get_config().log_dir, source, lines)}


@router.get("/stream")
async def stream_logs(request: Request, source: str = Query("streams")) -> StreamingResponse:
    """Live-tail a log source over SSE (only newly-appended lines)."""
    if source not in LOG_SOURCES:
        source = "streams"
    log_dir = get_config().log_dir

    async def event_generator():
        # Heartbeat keeps the SSE connection open through idle periods.
        gen = tail_stream(log_dir, source)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    line = await asyncio.wait_for(gen.__anext__(), timeout=15)
                    yield f"data: {line}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
                except StopAsyncIteration:
                    break
        finally:
            await gen.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
