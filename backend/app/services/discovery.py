"""Camera discovery service."""

from __future__ import annotations

import logging

from backend.app.models.camera import Camera
from backend.app.services.rhombus_api import RhombusClient

logger = logging.getLogger("edgecaster")


class DiscoveryService:
    """Manages camera discovery and caching."""

    def __init__(self) -> None:
        self._cameras: list[Camera] = []

    @property
    def cameras(self) -> list[Camera]:
        return list(self._cameras)

    def get_camera(self, uuid: str) -> Camera | None:
        for cam in self._cameras:
            if cam.uuid == uuid:
                return cam
        return None

    async def refresh(self, client: RhombusClient) -> list[Camera]:
        """Re-discover cameras from Rhombus API."""
        logger.info("Refreshing camera discovery")
        self._cameras = await client.get_cameras()
        logger.info("Discovery complete: %d cameras found", len(self._cameras))
        return self._cameras
