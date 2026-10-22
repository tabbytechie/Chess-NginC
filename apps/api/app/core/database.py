"""Database configuration and session management (REL-001/REL-002/REL-008)."""

import logging
from collections.abc import Generator
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.observability import configure_logging

# Settings load from this app's own .env, resolved from the package location so
# it works no matter which directory uvicorn/pytest was started from.
_API_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _API_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings with database configuration.

    Production rules (REL-001/REL-002): every secret comes from the environment;
    `secret_key` has no usable default — the app refuses to start with the
    development placeholder when APP_ENV=production.
    """

    app_env: str = "development"
    # Compose-shaped default: no developer username in tracked source. Local
    # out-of-container runs point at their own database via apps/api/.env.
    database_url: str = "postgresql+psycopg://chess:chess@localhost:5432/chess_engine"
    secret_key: str = "change-me-in-development-only"
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_ttl_hours: int = 24 * 7  # 7 days
    # Connection pool (REL-008): sized for the single-worker API process. pre_ping
    # transparently discards connections the server closed (e.g. after a restart).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True
    # Proxy-aware client identity for rate limiting (SEC-012): when the API runs
    # behind nginx, uvicorn must trust `X-Forwarded-For` from these IPs so the
    # limiter keys on the real client, not the shared proxy address. Empty means
    # direct exposure: use the socket peer and never trust forwarded headers.
    forwarded_allow_ips: str = ""
    # Split buckets per route class so one noisy class cannot exhaust another.
    auth_rate_limit_per_minute: int = 10
    engine_rate_limit_per_minute: int = 60
    write_rate_limit_per_minute: int = 120
    # Stockfish (BEN-001/002/004/006): absolute binary path, empty = PATH lookup.
    # Never accept a path from clients; only env/config (BEN-020).
    stockfish_path: str = ""
    stockfish_depth_limit: int = 15
    stockfish_time_limit_ms: int = 1000
    # Hosted Stockfish API (stockfishapi.com): cloud engine fallback when no
    # local binary exists. Key comes ONLY from env (.env, never committed);
    # empty = cloud provider disabled. Never log or return the key.
    stockfish_api_key: str = ""
    stockfish_api_base_url: str = "https://stockfishapi.com/v1"
    # Engine provider seam (Phase 2). `engine_backend` selects the opponent:
    #   stockfish_remote -> the private-network sidecar (production)
    #   stockfish_local  -> a locally installed Stockfish binary (dev)
    #   custom           -> the in-process fallback engine (always available)
    engine_backend: Literal["stockfish_remote", "stockfish_local", "custom"] = "custom"
    engine_base_url: str = "http://engine:8050"
    engine_connect_timeout_ms: int = 3000
    engine_read_timeout_ms: int = 8000
    # Global + per-user concurrency caps for live searches; saturation -> 503.
    engine_max_concurrency: int = 2
    engine_max_concurrency_per_user: int = 1
    # Circuit breaker: open after N consecutive backend failures for a cooldown.
    engine_circuit_failure_threshold: int = 3
    engine_circuit_cooldown_seconds: int = 30
    # Account recovery (SEC-013): email sender + token lifetimes. With no
    # `smtp_host`, the ConsoleEmailSender logs reset/verify URLs so local dev
    # needs zero configuration; SMTP activates only when those are set.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Public base URL used to build clickable verify/reset links. Empty falls
    # back to the request origin at the route layer.
    public_web_base_url: str = ""
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=_ENV_FILE)


settings = Settings()

if settings.app_env == "production" and settings.secret_key == "change-me-in-development-only":
    raise RuntimeError("REFUSE TO START: set a unique SECRET_KEY in production (REL-002).")

# Structured logging (REL-008): single-line JSON records to stdout.
configure_logging(settings.log_level)
logger = logging.getLogger("chess-engine-api")


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Create engine
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
