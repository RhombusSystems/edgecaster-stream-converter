"""Security utilities."""

from __future__ import annotations


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret string, showing only the last N characters.

    Examples:
        "abc123xyz" -> "***xyz"
        "ab"        -> "***"
        ""          -> "***"
    """
    if len(value) <= visible_chars:
        return "***"
    return "***" + value[-visible_chars:]
