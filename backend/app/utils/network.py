"""Network utility functions."""

from __future__ import annotations

import socket


def get_hostname() -> str:
    """Return the system hostname."""
    return socket.gethostname()


def get_local_ip() -> str:
    """Return the primary local IP address."""
    try:
        # Connect to an external address to determine the default interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
