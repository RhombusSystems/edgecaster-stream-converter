"""Camera models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CameraStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    @classmethod
    def from_rhombus(cls, connection_status: str | None) -> CameraStatus:
        """Map Rhombus DeviceStatusEnum to our status."""
        mapping = {
            "GREEN": cls.ONLINE,
            "YELLOW": cls.DEGRADED,
            "ORANGE": cls.DEGRADED,
            "RED": cls.OFFLINE,
        }
        return mapping.get(connection_status or "", cls.UNKNOWN)


class Camera(BaseModel):
    """Discovered camera from Rhombus."""

    uuid: str
    name: str
    location_uuid: str | None = None
    location_name: str = ""
    status: CameraStatus = CameraStatus.UNKNOWN
    lan_addresses: list[str] = []
    firmware_version: str = ""
    serial_number: str = ""
