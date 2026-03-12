"""Tests for RTSP path slug generation."""

from backend.app.utils.slugify import slugify


def test_basic_name():
    assert slugify("Front Door") == "front_door"


def test_parentheses():
    assert slugify("Warehouse (East)") == "warehouse_east"


def test_unicode():
    assert slugify("Cafe Entrance") == "cafe_entrance"


def test_special_characters():
    assert slugify("Loading Dock #2") == "loading_dock_2"


def test_multiple_spaces():
    assert slugify("Main   Lobby") == "main_lobby"


def test_leading_trailing():
    assert slugify("  Hallway  ") == "hallway"


def test_empty_string():
    assert slugify("") == "unnamed"


def test_only_special():
    assert slugify("###") == "unnamed"


def test_numbers():
    assert slugify("Camera 42") == "camera_42"


def test_already_slug():
    assert slugify("front_door") == "front_door"


def test_mixed_case():
    assert slugify("PARKING Garage Level-3") == "parking_garage_level_3"


def test_deterministic():
    """Same input always produces same output."""
    name = "Conference Room B"
    assert slugify(name) == slugify(name)
