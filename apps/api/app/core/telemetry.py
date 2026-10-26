"""Telemetry foundation (Phase 12A, decision D14): JSON logs, request ids, metrics.

One small module that everything else points at — it imports nothing from
``app``, so engine, api and games layers can all use it without cycles. The
Prometheus default registry is deliberate: the app runs as a single process
(D6), so no multiproc mode is needed, and `/metrics` is scraped by the host.

Bespoke instruments exist only for the things that actually hurt in this app
(market-plan MON-003..007); per-route RED metrics come free from the
instrumentator wired in ``app.main``. Never add a label a user controls —
label cardinality is a memory leak waiting to happen.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

# --- request ids + JSON logs (MON-001) -------------------------------------------

# Set by the HTTP middleware in app.main for every request; the JSON formatter
# reads it directly, so log calls anywhere in the process carry it without
# threading a parameter through every layer.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Keys a caller may attach via `extra` for the structured access line; anything
# else on the record is standard LogRecord furniture and never serialized.
_ACCESS_KEYS = ("method", "path", "status", "duration_ms")


def new_request_id() -> str:
    """A short opaque id; unique enough for correlating one request's lines."""
    return uuid.uuid4().hex[:16]


class JsonFormatter(logging.Formatter):
    """One JSON object per line: what a log agent wants, and still greppable."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            entry["request_id"] = request_id
        access = getattr(record, "http_access", None)
        if isinstance(access, dict):
            entry["http"] = {k: access.get(k) for k in _ACCESS_KEYS}
        # RB-003: the one boot-time structured line carries the resolved env
        # files + engine/voice mode. Without this the fixed key set above would
        # silently drop it and preflight would log nothing but its own name.
        preflight = getattr(record, "preflight", None)
        if isinstance(preflight, dict):
            entry["preflight"] = preflight
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str, json_logs: bool) -> None:
    """Replace the root logger setup (called once from core.database).

    JSON lines are the shipped default (MON-001); ``LOG_JSON=false`` restores
    the human-readable single-line format for anyone tailing a terminal raw.
    The QA-019 rule stands either way: no secrets or session tokens are ever
    logged — there is nothing here that writes request headers or bodies.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


access_logger = logging.getLogger("chess-engine-api.access")

# --- bespoke metrics (MON-003..007) ----------------------------------------------

# Buckets aimed at the two real engine paths: a play move (sub-second to ~1 s)
# and a whole review batch (seconds to minutes). `provider` separates local
# from hosted so one dashboard answers "why is review slow" vs "is the pot empty".
ENGINE_ANALYSE_SECONDS = Histogram(
    "engine_analyse_seconds",
    "Wall time of an engine analyse call (or whole batch) by provider.",
    ("provider",),
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160, 320),
)
ENGINE_UNAVAILABLE_TOTAL = Counter(
    "engine_unavailable_total",
    "Engine failures: no binary and no key, or a provider that died mid-call (D7 503s).",
)
RATE_LIMIT_REJECTIONS_TOTAL = Counter(
    "rate_limit_rejections_total",
    "429s issued per limiter bucket (auth/moves/assistant/review/training).",
    ("bucket",),
)
CLOUD_UNITS_USED_TODAY = Gauge(
    "cloud_units_used_today",
    "Hosted-engine units consumed so far in the current UTC day (the shared pot).",
)
CLOUD_UPSTREAM_ERRORS_TOTAL = Counter(
    "cloud_upstream_errors_total",
    "Non-2xx answers from the hosted engine API, by status code (402/429 = plan trouble).",
    ("status",),
)
WS_CONNECTIONS_ACTIVE = Gauge(
    "ws_connections_active",
    "Live online-play sockets in this process's hub (the D6 state island).",
)


@contextlib.contextmanager
def engine_timer(provider: str | Callable[[], str]) -> Iterator[None]:
    """Observe the wrapped engine call on ENGINE_ANALYSE_SECONDS.

    ``provider`` may be a callable resolved after the call (the factory label is
    only trustworthy once the object is open); pass the string otherwise.
    """
    start = time.perf_counter()
    yield
    name = provider() if callable(provider) else provider
    ENGINE_ANALYSE_SECONDS.labels(provider=name).observe(time.perf_counter() - start)


def record_engine_unavailable() -> None:
    ENGINE_UNAVAILABLE_TOTAL.inc()


def record_rate_limit_rejection(bucket: str) -> None:
    RATE_LIMIT_REJECTIONS_TOTAL.labels(bucket=bucket).inc()


def set_cloud_units_used_today(count: int) -> None:
    CLOUD_UNITS_USED_TODAY.set(count)


def record_cloud_upstream_error(status: int) -> None:
    CLOUD_UPSTREAM_ERRORS_TOTAL.labels(status=str(status)).inc()


def set_ws_connections(count: int) -> None:
    WS_CONNECTIONS_ACTIVE.set(count)
