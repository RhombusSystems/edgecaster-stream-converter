"""Deterministic slug generation for RTSP paths."""

from __future__ import annotations

import re
import unicodedata


def slugify(name: str) -> str:
    """Convert a camera name to a deterministic, URL-safe RTSP path slug.

    Examples:
        "Front Door"       -> "front_door"
        "Warehouse (East)" -> "warehouse_east"
        "Café Entrance"    -> "cafe_entrance"
        ""                 -> "unnamed"
    """
    # Normalize unicode characters
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Lowercase
    value = value.lower()
    # Replace any non-alphanumeric chars with underscores
    value = re.sub(r"[^a-z0-9]+", "_", value)
    # Strip leading/trailing underscores
    value = value.strip("_")
    # Collapse multiple underscores
    value = re.sub(r"_+", "_", value)
    return value or "unnamed"
