"""Process-wide engine runtime (Phase 2).

Holds the single provider graph and the single search limiter so every request
shares one connection pool, one circuit breaker, and one concurrency budget.
Built lazily from settings on first use, with an override seam for tests.
"""

from __future__ import annotations

import threading

from app.core.database import settings
from app.engine.circuit import SearchLimiter
from app.engine.factory import build_engine_provider
from app.engine.provider import EngineProvider

_lock = threading.Lock()
_provider: EngineProvider | None = None
_limiter: SearchLimiter | None = None


def get_engine_provider() -> EngineProvider:
    """Return the shared engine provider, building it once from settings."""
    global _provider
    with _lock:
        if _provider is None:
            _provider = build_engine_provider(settings)
        return _provider


def get_search_limiter() -> SearchLimiter:
    """Return the shared concurrency limiter, building it once from settings."""
    global _limiter
    with _lock:
        if _limiter is None:
            _limiter = SearchLimiter(
                max_concurrent=settings.engine_max_concurrency,
                max_per_user=settings.engine_max_concurrency_per_user,
            )
        return _limiter


def set_engine_provider_override(provider: EngineProvider | None) -> None:
    """Test seam: force a specific provider (or clear the override with None)."""
    global _provider
    with _lock:
        _provider = provider


def reset_engine_runtime() -> None:
    """Drop cached provider/limiter and release resources (tests and shutdown)."""
    global _provider, _limiter
    with _lock:
        provider = _provider
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        _provider = None
        _limiter = None
