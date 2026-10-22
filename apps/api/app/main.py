"""FastAPI application entry point."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.games import router as games_router
from app.api.v1.health import router as health_router
from app.core.database import settings
from app.core.observability import new_request_id, request_id_ctx

API_V1_PREFIX = "/api/v1"

access_logger = logging.getLogger("chess-engine-api.access")

app = FastAPI(title="Chess Engine API", version="0.1.0")


def _resolve_request_id(request: Request) -> str:
    """Reuse a trusted proxy's request id, else mint one (REL-008)."""
    inbound = request.headers.get("x-request-id")
    return inbound if inbound and len(inbound) <= 64 else new_request_id()


# Explicit CORS allowlist from settings (SEC-014); no wildcard with cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(health_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(games_router, prefix=API_V1_PREFIX)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Tag every request with a correlation id, echoed on the response.

    The id lives in a context var so log records emitted anywhere during the
    request carry it without threading it through every call signature.
    """
    rid = _resolve_request_id(request)
    token = request_id_ctx.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = rid
    # Log the completion under the same request id (no body, no secrets).
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    access_logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/")
def root() -> dict[str, str]:
    """Return a minimal root response."""
    return {"service": "chess-engine-api", "docs": "/docs"}
