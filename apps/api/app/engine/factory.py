"""Build the configured engine provider (Phase 2).

One function turns settings into an :class:`EngineProvider`. Non-custom backends
are wrapped in :class:`ResilientEngineProvider` so the custom engine is always
the safety net; ``custom`` is returned bare because there is nothing to fail
over to. The service layer only ever sees the ``EngineProvider`` protocol.
"""

from __future__ import annotations

from app.core.database import Settings
from app.engine.circuit import CircuitBreaker, ResilientEngineProvider
from app.engine.custom_provider import CustomEngineProvider
from app.engine.local_stockfish import LocalStockfishProvider
from app.engine.provider import EngineProvider
from app.engine.remote_stockfish import RemoteStockfishProvider
from app.engine.stockfish import StockfishConfig


def build_engine_provider(settings: Settings) -> EngineProvider:
    """Construct the engine provider graph for the configured backend."""
    fallback = CustomEngineProvider()
    backend = settings.engine_backend
    if backend == "custom":
        return fallback

    breaker = CircuitBreaker(
        failure_threshold=settings.engine_circuit_failure_threshold,
        cooldown_seconds=settings.engine_circuit_cooldown_seconds,
    )
    if backend == "stockfish_remote":
        primary: EngineProvider = RemoteStockfishProvider(
            settings.engine_base_url,
            connect_timeout_ms=settings.engine_connect_timeout_ms,
            read_timeout_ms=settings.engine_read_timeout_ms,
        )
    else:  # stockfish_local
        primary = LocalStockfishProvider(StockfishConfig(path=settings.stockfish_path))
    return ResilientEngineProvider(primary, fallback, breaker)
