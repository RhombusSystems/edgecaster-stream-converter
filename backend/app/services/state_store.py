"""Persistent state store for EdgeCaster."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger("edgecaster")


class StateStore:
    """Thread-safe JSON file-based state persistence."""

    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / "state.json"
        self._lock = Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data = json.load(f)
                logger.info("State loaded from %s", self._path)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state file, starting fresh: %s", e)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save state: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._save()

    # Convenience methods for stream state

    def get_enabled_cameras(self) -> set[str]:
        """Return the set of camera UUIDs that should be streaming."""
        return set(self.get("enabled_cameras", []))

    def set_enabled_cameras(self, camera_uuids: set[str]) -> None:
        self.set("enabled_cameras", sorted(camera_uuids))

    def get_slug_map(self) -> dict[str, str]:
        """Return camera_uuid -> rtsp_slug mapping."""
        return dict(self.get("slug_map", {}))

    def set_slug_map(self, slug_map: dict[str, str]) -> None:
        self.set("slug_map", slug_map)
