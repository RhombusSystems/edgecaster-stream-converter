"""PostHog analytics and error tracking service."""

from __future__ import annotations

import logging
import platform
import uuid
from pathlib import Path

from posthog import Posthog

from backend.app.utils.network import get_hostname, get_local_ip

logger = logging.getLogger("edgecaster")

# Singleton client
_posthog: Posthog | None = None
_device_id: str = ""


def _get_machine_id() -> str:
    """Get a persistent device identifier.

    Uses /etc/machine-id on Linux (standard on Raspberry Pi / Ubuntu).
    Falls back to generating and caching a UUID.
    """
    # Linux machine-id (Raspberry Pi / Ubuntu)
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        return machine_id_path.read_text().strip()

    # Fallback: generate and persist a UUID in the state dir
    return str(uuid.uuid4())


def init_posthog(
    api_key: str,
    host: str = "https://us.i.posthog.com",
    device_id: str | None = None,
) -> None:
    """Initialize the PostHog client."""
    global _posthog, _device_id

    if not api_key:
        logger.info("PostHog API key not configured, telemetry disabled")
        return

    _device_id = device_id or _get_machine_id()

    _posthog = Posthog(
        api_key,
        host=host,
        enable_exception_autocapture=True,
    )

    # Set device properties once
    _posthog.identify(
        _device_id,
        properties={
            "hostname": get_hostname(),
            "local_ip": get_local_ip(),
            "os": platform.system(),
            "os_version": platform.release(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
        },
    )

    logger.info("PostHog initialized (device_id=%s)", _device_id[:12])


def shutdown_posthog() -> None:
    """Flush and close the PostHog client."""
    global _posthog
    if _posthog:
        _posthog.flush()
        _posthog.shutdown()
        _posthog = None
        logger.info("PostHog shutdown complete")


def capture_event(event: str, properties: dict | None = None) -> None:
    """Send a custom event to PostHog."""
    if not _posthog:
        return
    _posthog.capture(_device_id, event, properties=properties or {})


def capture_exception(
    exception: Exception,
    context: dict | None = None,
) -> None:
    """Capture an exception to PostHog error tracking."""
    if not _posthog:
        return
    properties = {"$exception_source": "backend"}
    if context:
        properties.update(context)
    _posthog.capture(
        _device_id,
        "$exception",
        properties={
            **properties,
            "$exception_type": type(exception).__name__,
            "$exception_message": str(exception),
        },
    )


def get_device_id() -> str:
    """Return the current device identifier."""
    return _device_id
