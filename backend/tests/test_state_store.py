"""Tests for persistent state store."""

import json
import tempfile
from pathlib import Path

from backend.app.services.state_store import StateStore


def test_set_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir))
        store.set("key", "value")
        assert store.get("key") == "value"


def test_get_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir))
        assert store.get("missing") is None
        assert store.get("missing", "default") == "default"


def test_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)

        store1 = StateStore(path)
        store1.set("persistent", True)

        # Reload from disk
        store2 = StateStore(path)
        assert store2.get("persistent") is True


def test_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir))
        store.set("key", "value")
        store.delete("key")
        assert store.get("key") is None


def test_enabled_cameras():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir))

        assert store.get_enabled_cameras() == set()

        cameras = {"uuid1", "uuid2", "uuid3"}
        store.set_enabled_cameras(cameras)
        assert store.get_enabled_cameras() == cameras


def test_slug_map():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir))

        assert store.get_slug_map() == {}

        slug_map = {"uuid1": "front_door", "uuid2": "warehouse"}
        store.set_slug_map(slug_map)
        assert store.get_slug_map() == slug_map


def test_corrupted_file_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "state.json"
        path.write_text("not valid json{{{")

        store = StateStore(Path(tmpdir))
        assert store.get("anything") is None
        # Should still work after recovery
        store.set("key", "value")
        assert store.get("key") == "value"
