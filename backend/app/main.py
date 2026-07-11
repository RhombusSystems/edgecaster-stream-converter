"""EdgeCaster FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import load_config
from backend.app.dependencies import init_services
from backend.app.logging_setup import setup_logging
from backend.app.routers import auth, cameras, settings, streams, system
from backend.app.services.alerts import AlertManager
from backend.app.services.discovery import DiscoveryService
from backend.app.services.health import MetricsCollector
from backend.app.services.mediamtx import get_path_stats
from backend.app.services.posthog_service import (
    capture_event,
    capture_exception,
    init_posthog,
    shutdown_posthog,
)
from backend.app.services.rhombus_api import RhombusClient
from backend.app.services.state_store import StateStore
from backend.app.services.stream_manager import StreamManager
from backend.app.services.watchdog import notify_ready, notify_stopping, watchdog_loop

logger = logging.getLogger("edgecaster")

METRICS_INTERVAL = 2  # seconds between metric samples / MediaMTX polls / alert evals


async def metrics_loop(
    config,
    stream_manager: StreamManager,
    discovery: DiscoveryService,
    collector: MetricsCollector,
    alert_manager: AlertManager,
) -> None:
    """Single sampler feeding the SSE stream and the alert evaluator."""
    while True:
        try:
            # Per-stream throughput/liveness from the MediaMTX control API.
            path_stats = await get_path_stats(
                config.mediamtx_api_host, config.mediamtx_api_port
            )
            if path_stats:
                stream_manager.apply_path_stats(path_stats)

            status = await collector.sample(
                total_cameras=len(discovery.cameras),
                active_streams=stream_manager.active_count,
                max_streams=config.max_streams,
                alerts=None,
            )
            await alert_manager.evaluate_system(status)
            # Reflect current active alerts in the cached snapshot (same object
            # stored as collector.latest, so the SSE stream sees them).
            status.alerts = alert_manager.get_active()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - metrics must never crash the app
            logger.debug("metrics loop iteration failed: %s", e)
        await asyncio.sleep(METRICS_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Load config
    config = load_config()
    setup_logging(config.log_dir, dev_mode=config.dev_mode)
    logger.info("EdgeCaster starting up (dev_mode=%s)", config.dev_mode)

    # Initialize PostHog telemetry
    init_posthog(config.posthog_api_key, config.posthog_host)

    # Initialize services
    state_store = StateStore(config.state_dir)
    discovery = DiscoveryService()
    stream_manager = StreamManager(config, state_store)
    alert_manager = AlertManager(config)
    metrics_collector = MetricsCollector()
    stream_manager.set_alert_manager(alert_manager)

    # Initialize Rhombus client if API key is configured
    rhombus_client: RhombusClient | None = None
    if config.api_key:
        rhombus_client = RhombusClient(config.api_key)
        stream_manager.set_rhombus_client(rhombus_client)

        # Discover cameras
        try:
            await discovery.refresh(rhombus_client)
        except Exception as e:
            logger.error("Initial camera discovery failed: %s", e)

        # Restore previously enabled streams
        camera_map = {cam.uuid: cam.name for cam in discovery.cameras}
        try:
            await stream_manager.restore_streams(camera_map)
        except Exception as e:
            logger.error("Stream restoration failed: %s", e)

    # Register singletons for dependency injection
    init_services(
        config,
        state_store,
        stream_manager,
        discovery,
        rhombus_client,
        alert_manager,
        metrics_collector,
    )

    # Start background tasks
    watchdog_task = asyncio.create_task(watchdog_loop(), name="watchdog")
    health_task = asyncio.create_task(
        stream_manager.health_check_loop(), name="health-check"
    )
    metrics_task = asyncio.create_task(
        metrics_loop(config, stream_manager, discovery, metrics_collector, alert_manager),
        name="metrics",
    )

    notify_ready()
    logger.info("EdgeCaster ready")
    capture_event("device_boot", {
        "dev_mode": config.dev_mode,
        "max_streams": config.max_streams,
        "api_key_configured": bool(config.api_key),
        "restored_streams": stream_manager.active_count,
    })
    yield

    # Shutdown
    notify_stopping()
    logger.info("EdgeCaster shutting down")
    watchdog_task.cancel()
    health_task.cancel()
    metrics_task.cancel()
    await stream_manager.shutdown()
    if rhombus_client:
        await rhombus_client.close()
    capture_event("device_shutdown")
    shutdown_posthog()
    logger.info("EdgeCaster shutdown complete")


app = FastAPI(
    title="EdgeCaster",
    description="Rhombus Secure Raw Stream to RTSP converter",
    version="1.0.0",
    lifespan=lifespan,
)


# Global exception handler — report unhandled errors to PostHog
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    capture_exception(exc, {"path": request.url.path, "method": request.method})
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(streams.router)
app.include_router(settings.router)
app.include_router(system.router)

# Serve frontend static files in production
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
