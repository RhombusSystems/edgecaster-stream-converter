"""FastAPI dependency injection."""

from __future__ import annotations

from backend.app.config import EdgeCasterConfig
from backend.app.services.alerts import AlertManager
from backend.app.services.discovery import DiscoveryService
from backend.app.services.health import MetricsCollector
from backend.app.services.rhombus_api import RhombusClient
from backend.app.services.state_store import StateStore
from backend.app.services.stream_manager import StreamManager
from backend.app.services.tunnel import TunnelManager

# Global singletons — initialized during app lifespan
_config: EdgeCasterConfig | None = None
_state_store: StateStore | None = None
_stream_manager: StreamManager | None = None
_discovery: DiscoveryService | None = None
_rhombus_client: RhombusClient | None = None
_alert_manager: AlertManager | None = None
_metrics_collector: MetricsCollector | None = None
_tunnel_manager: TunnelManager | None = None


def init_services(
    config: EdgeCasterConfig,
    state_store: StateStore,
    stream_manager: StreamManager,
    discovery: DiscoveryService,
    rhombus_client: RhombusClient | None,
    alert_manager: AlertManager | None = None,
    metrics_collector: MetricsCollector | None = None,
    tunnel_manager: TunnelManager | None = None,
) -> None:
    global _config, _state_store, _stream_manager, _discovery, _rhombus_client
    global _alert_manager, _metrics_collector, _tunnel_manager
    _config = config
    _state_store = state_store
    _stream_manager = stream_manager
    _discovery = discovery
    _rhombus_client = rhombus_client
    _alert_manager = alert_manager
    _metrics_collector = metrics_collector
    _tunnel_manager = tunnel_manager


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


def get_alert_manager() -> AlertManager:
    assert _alert_manager is not None
    return _alert_manager


def get_metrics_collector() -> MetricsCollector:
    assert _metrics_collector is not None
    return _metrics_collector


def get_tunnel_manager() -> TunnelManager:
    assert _tunnel_manager is not None
    return _tunnel_manager
