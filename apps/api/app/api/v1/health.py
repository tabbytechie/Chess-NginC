"""Health-check endpoints: liveness + readiness (REL-007).

`/health` is a cheap liveness probe (the process is up). `/ready` is the load-
balancer gate: it returns 503 when the app cannot serve traffic — today that
means the database is unreachable. The Stockfish sidecar is reported but never
fatal: a sidecar outage degrades the opponent to the in-process fallback, so the
site stays ready while search quality drops.
"""

import logging

import httpx
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.schemas import ReadinessResponse
from app.core.database import engine, settings

logger = logging.getLogger("chess-engine-api.health")

router = APIRouter(tags=["health"])

# Kept short: readiness must answer fast so a load balancer never stalls on us.
_ENGINE_PROBE_TIMEOUT_S = 2.0


@router.get("/health")
def health() -> dict[str, str]:
    """Report service liveness."""
    return {"status": "ok"}


def _database_up() -> bool:
    """True when the database answers a trivial query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - exercised via monkeypatch in tests
        logger.warning("readiness: database unreachable", exc_info=True)
        return False
    return True


def _engine_status() -> str:
    """Report the opponent backend without ever failing readiness.

    * ``custom``  -> ``builtin`` (the in-process engine, always available)
    * ``stockfish_local`` -> ``local`` (a host binary, no network to probe)
    * ``stockfish_remote`` -> ``up``/``degraded`` from a quick sidecar ping
    """
    backend = settings.engine_backend
    if backend == "custom":
        return "builtin"
    if backend == "stockfish_local":
        return "local"
    url = f"{settings.engine_base_url.rstrip('/')}/healthz"
    try:
        resp = httpx.get(url, timeout=_ENGINE_PROBE_TIMEOUT_S)
        return "up" if resp.status_code < 400 else "degraded"
    except httpx.HTTPError:
        # Unreachable sidecar is a degraded opponent, not a down site.
        return "degraded"


@router.get(
    "/ready",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {"model": ReadinessResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse},
    },
)
def ready() -> JSONResponse:
    """Report readiness: 200 when the database is reachable, else 503 (REL-007)."""
    if not _database_up():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not-ready", "database": "down", "engine": _engine_status()},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready", "database": "up", "engine": _engine_status()},
    )
