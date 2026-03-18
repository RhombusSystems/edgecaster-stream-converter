"""Rhombus API client for camera discovery and stream management."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.models.camera import Camera, CameraStatus
from backend.app.services.posthog_service import capture_exception

logger = logging.getLogger("edgecaster.rhombus_api")

BASE_URL = "https://api2.rhombussystems.com"

# Rate limit: 1000 req/hr, 100 req/min burst
REQUEST_TIMEOUT = 30.0


class RhombusAPIError(Exception):
    """Raised when a Rhombus API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RhombusClient:
    """Async client for Rhombus API operations."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "x-auth-scheme": "api-token",
                "x-auth-apikey": api_key,
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        """Make an authenticated POST request to the Rhombus API."""
        try:
            resp = await self._client.post(f"/api{path}", json=body or {})
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RhombusAPIError(
                    data.get("errorMsg", "Unknown Rhombus API error"),
                    status_code=resp.status_code,
                )
            return data
        except httpx.HTTPStatusError as e:
            logger.error("Rhombus API HTTP error: %s %s", e.response.status_code, path)
            exc = RhombusAPIError(
                f"HTTP {e.response.status_code}: {path}", status_code=e.response.status_code
            )
            capture_exception(exc, {"api_path": path, "status_code": e.response.status_code})
            raise exc from e
        except httpx.RequestError as e:
            logger.error("Rhombus API request error: %s", e)
            exc = RhombusAPIError(f"Request failed: {e}")
            capture_exception(exc, {"api_path": path})
            raise exc from e

    async def get_cameras(self) -> list[Camera]:
        """Discover all cameras in the organization."""
        logger.info("Discovering cameras via Rhombus API")

        # Fetch camera states
        data = await self._post("/camera/getMinimalCameraStateList")
        camera_states = data.get("cameraStates", [])

        # Fetch location labels for name resolution
        location_map = await self._get_location_labels()

        cameras: list[Camera] = []
        for state in camera_states:
            uuid = state.get("uuid", "")
            if not uuid:
                continue

            location_uuid = state.get("locationUuid")
            cameras.append(
                Camera(
                    uuid=uuid,
                    name=state.get("name", "Unnamed Camera"),
                    location_uuid=location_uuid,
                    location_name=location_map.get(location_uuid, "") if location_uuid else "",
                    status=CameraStatus.from_rhombus(state.get("connectionStatus")),
                    lan_addresses=state.get("lanAddresses") or [],
                    firmware_version=state.get("firmwareVersion", ""),
                    serial_number=state.get("serialNumber", ""),
                )
            )

        logger.info("Discovered %d cameras", len(cameras))
        return cameras

    async def _get_location_labels(self) -> dict[str, str]:
        """Fetch location UUID -> name mapping."""
        try:
            data = await self._post("/location/getLocationLabelsForOrg")
            labels = data.get("locationLabels", {})
            # API returns { uuid: { "name": "...", ... } } or similar
            result: dict[str, str] = {}
            if isinstance(labels, dict):
                for uuid, info in labels.items():
                    if isinstance(info, dict):
                        result[uuid] = info.get("name", "")
                    elif isinstance(info, str):
                        result[uuid] = info
            return result
        except RhombusAPIError:
            logger.warning("Failed to fetch location labels, continuing without them")
            return {}

    async def create_raw_stream(self, camera_uuid: str, stream_name: str) -> str:
        """Create a Secure Raw Stream and return the LAN video URL.

        Args:
            camera_uuid: The camera UUID (without facet suffix).
            stream_name: A descriptive name for the stream.

        Returns:
            The lanVideoUrl for FFmpeg to pull from.
        """
        device_uuid = f"{camera_uuid}.v0"
        logger.info("Creating raw HTTP stream for device %s", device_uuid)

        data = await self._post(
            "/camera/createRawHttpStream",
            {
                "deviceUuid": device_uuid,
                "rawStreamName": stream_name,
                "streamType": "USER",
            },
        )

        lan_video_url = data.get("lanVideoUrl", "")
        if not lan_video_url:
            raise RhombusAPIError(
                f"No lanVideoUrl returned for device {device_uuid}. "
                "The camera may not support raw HTTP streams or may be offline."
            )

        logger.info("Raw stream created for %s: %s", device_uuid, lan_video_url)
        return lan_video_url

    async def delete_raw_stream(self, camera_uuid: str) -> None:
        """Delete raw HTTP streams for a camera."""
        device_uuid = f"{camera_uuid}.v0"
        logger.info("Deleting raw HTTP streams for device %s", device_uuid)
        try:
            await self._post(
                "/camera/deleteRawHttpStream",
                {"deviceUuid": device_uuid},
            )
        except RhombusAPIError as e:
            logger.warning("Failed to delete raw stream for %s: %s", device_uuid, e)

    async def get_raw_streams(self, camera_uuid: str) -> list[dict[str, Any]]:
        """Get existing raw HTTP streams for a camera."""
        device_uuid = f"{camera_uuid}.v0"
        data = await self._post(
            "/camera/getRawHttpStreams",
            {"deviceUuid": device_uuid},
        )
        return data.get("rawHttpStreams", [])

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a lightweight API call."""
        try:
            await self._post("/camera/getMinimalCameraStateList")
            return True
        except RhombusAPIError:
            return False
