"""FastAPI application entry point."""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import Response

from app.api.v1.achievements import router as achievements_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.games import router as games_router
from app.api.v1.health import router as health_router
from app.api.v1.online import router as online_router
from app.api.v1.training import router as training_router
from app.api.v1.tts import router as tts_router
from app.core.database import settings
from app.core.telemetry import access_logger, new_request_id, request_id_var

API_V1_PREFIX = "/api/v1"

# Paths kept out of the access log: the compose healthcheck and the Prometheus
# scrape both fire every few seconds and would bury real lines.
_QUIET_PATHS = {"/api/v1/health", "/api/v1/ready", "/metrics"}

app = FastAPI(title="Chess Engine API", version="0.1.0")

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
app.include_router(online_router, prefix=API_V1_PREFIX)
app.include_router(achievements_router, prefix=API_V1_PREFIX)
app.include_router(training_router, prefix=API_V1_PREFIX)
app.include_router(assistant_router, prefix=API_V1_PREFIX)
app.include_router(tts_router, prefix=API_V1_PREFIX)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Stamp one request id (inbound X-Request-ID wins), log one access line.

    The id rides the ContextVar the JSON log formatter reads, so every line
    this request produces carries it (MON-001). Only method/path/status/duration
    are logged — never headers, cookies or bodies (QA-019).
    """
    rid = request.headers.get("x-request-id") or new_request_id()
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    if request.url.path not in _QUIET_PATHS:
        access_logger.info(
            "request",
            extra={
                "http_access": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
    return response


# Prometheus RED metrics per route + the /metrics scrape endpoint (D14/MON-002).
# Scrape the api port directly (8000:/metrics); it is deliberately not proxied
# through the web container, so it never faces browser traffic — and it stays
# out of the OpenAPI spec (the contract test types every documented operation;
# a plaintext scrape endpoint has no response model to declare).
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/")
def root() -> dict[str, str]:
    """Return a minimal root response."""
    return {"service": "chess-engine-api", "docs": "/docs"}
