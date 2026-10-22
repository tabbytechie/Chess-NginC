"""Engine resilience: circuit breaker, search limiter, fallback wrapper (Phase 2).

A sidecar outage must degrade, not 500. Three small pieces:

* :class:`CircuitBreaker` — after N consecutive backend failures it opens for a
  cooldown window so we stop hammering a downed engine and log exactly once.
* :class:`SearchLimiter` — a global ``BoundedSemaphore`` plus a per-user cap. A
  saturated engine returns ``EngineSaturatedError`` (→ 503 + Retry-After) instead
  of piling up unbounded searches.
* :class:`ResilientEngineProvider` — wraps a primary backend with the custom
  engine as the fallback and the breaker between them. The service always gets a
  move unless every backend is broken.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.engine.domain import EngineDifficulty, EngineResult
from app.engine.errors import EngineSaturatedError, EngineUnavailableError
from app.engine.provider import AnalyseRequest, AnalysisResult, EngineProvider

logger = logging.getLogger("chess-engine-api")


class CircuitBreaker:
    """Consecutive-failure breaker with a fixed cooldown window."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = max(1, failure_threshold)
        self._cooldown = max(0.0, cooldown_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self._consecutive = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        """True if a call to the primary backend is permitted."""
        with self._lock:
            if self._opened_at is None:
                return True
            if self._clock() - self._opened_at >= self._cooldown:
                # Cooldown elapsed: close again so one probe is allowed.
                self._opened_at = None
                self._consecutive = 0
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._consecutive = 0
            self._opened_at = None

    def record_failure(self) -> bool:
        """Register a failure; True only on the transition into the open state."""
        with self._lock:
            self._consecutive += 1
            if self._consecutive >= self._threshold and self._opened_at is None:
                self._opened_at = self._clock()
                return True
            return False


class SearchLimiter:
    """Global + per-user concurrency guard for live searches."""

    def __init__(self, *, max_concurrent: int = 2, max_per_user: int = 1) -> None:
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrent))
        self._max_per_user = max(1, max_per_user)
        self._lock = threading.Lock()
        self._per_user: defaultdict[int, int] = defaultdict(int)

    @contextmanager
    def slot(self, user_id: int) -> Iterator[None]:
        """Acquire a global slot and a per-user slot, or raise ``EngineSaturatedError``."""
        if not self._semaphore.acquire(blocking=False):
            raise EngineSaturatedError("Engine concurrency limit reached")
        holding_user = False
        try:
            with self._lock:
                if self._per_user[user_id] >= self._max_per_user:
                    raise EngineSaturatedError("Per-user engine limit reached")
                self._per_user[user_id] += 1
                holding_user = True
            yield
        finally:
            if holding_user:
                with self._lock:
                    self._per_user[user_id] -= 1
                    if self._per_user[user_id] <= 0:
                        del self._per_user[user_id]
            self._semaphore.release()


class ResilientEngineProvider:
    """Primary backend with a custom-engine fallback behind a circuit breaker."""

    def __init__(
        self,
        primary: EngineProvider,
        fallback: EngineProvider,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._breaker = breaker or CircuitBreaker()

    @property
    def name(self) -> str:
        """Report the primary backend name (what we intended to use)."""
        return self._primary.name

    def close(self) -> None:
        """Release the primary backend's resources (e.g. the sidecar HTTP pool)."""
        close = getattr(self._primary, "close", None)
        if callable(close):
            close()

    def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
        """Try the primary backend; on unavailable (or open circuit) use fallback."""
        if self._breaker.allow():
            try:
                result = self._primary.move_for(fen, level=level)
                self._breaker.record_success()
                return result
            except EngineUnavailableError as exc:
                self._warn_if_opened(exc)
        return self._fallback.move_for(fen, level=level)

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Analysis mirrors :meth:`move_for` — degrade to the custom engine."""
        if self._breaker.allow():
            try:
                result = self._primary.analyse(request)
                self._breaker.record_success()
                return result
            except EngineUnavailableError as exc:
                self._warn_if_opened(exc)
        return self._fallback.analyse(request)

    def _warn_if_opened(self, exc: Exception) -> None:
        """Log once, when this failure tips the breaker into the open state."""
        if self._breaker.record_failure():
            logger.warning(
                "Engine backend %s unavailable (%s); falling back to %s for the cooldown window",
                self._primary.name,
                exc,
                self._fallback.name,
            )
