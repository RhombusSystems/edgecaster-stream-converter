"""FastAPI dependency injection."""

from __future__ import annotations

from fastapi import Cookie, HTTPException, status

from backend.app.auth import verify_session_token
from backend.app.config import EdgeCasterConfig
from backend.app.services.discovery import DiscoveryService
from backend.app.services.rhombus_api import RhombusClient
from backend.app.services.state_store import StateStore
from backend.app.services.stream_manager import StreamManager

# Global singletons — initialized during app lifespan
_config: EdgeCasterConfig | None = None
_state_store: StateStore | None = None
_stream_manager: StreamManager | None = None
_discovery: DiscoveryService | None = None
_rhombus_client: RhombusClient | None = None


def init_services(
    config: EdgeCasterConfig,
    state_store: StateStore,
    stream_manager: StreamManager,
    discovery: DiscoveryService,
    rhombus_client: RhombusClient | None,
) -> None:
    global _config, _state_store, _stream_manager, _discovery, _rhombus_client
    _config = config
    _state_store = state_store
    _stream_manager = stream_manager
    _discovery = discovery
    _rhombus_client = rhombus_client


def set_rhombus_client(client: RhombusClient | None) -> None:
    global _rhombus_client
    _rhombus_client = client


def get_config() -> EdgeCasterConfig:
    assert _config is not None
    return _config


def get_state_store() -> StateStore:
    assert _state_store is not None
    return _state_store


def get_stream_manager() -> StreamManager:
    assert _stream_manager is not None
    return _stream_manager


def get_discovery() -> DiscoveryService:
    assert _discovery is not None
    return _discovery


def get_rhombus_client() -> RhombusClient | None:
    return _rhombus_client


async def require_auth(session: str | None = Cookie(default=None)) -> None:
    """Dependency that enforces authentication on protected routes."""
    if _config is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    if not _config.admin_password_hash:
        # First-run: no password set yet, allow access to setup endpoints
        return

    if not session or not verify_session_token(session, _config.session_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
