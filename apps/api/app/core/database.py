"""Database configuration and session management (REL-001/REL-002/REL-008)."""

import logging
from collections.abc import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import telemetry


class Settings(BaseSettings):
    """Application settings with database configuration.

    Production rules (REL-001/REL-002): every secret comes from the environment;
    `secret_key` has no usable default — the app refuses to start with the
    development placeholder when APP_ENV=production.
    """

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://tabbymichael@localhost:5432/chess"
    secret_key: str = "change-me-in-development-only"
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_ttl_hours: int = 24 * 7  # 7 days
    auth_rate_limit_per_minute: int = 10
    # Online move spam guard (online-plan §6.1), per user per minute.
    move_rate_limit_per_minute: int = 60
    # Cost-tiered limiters (Phase 12A, D15): a review holds a warm engine for
    # seconds of CPU, so it is budgeted per hour and a forced re-run counts
    # double; training attempts write ledger rows, so they get a modest ceiling.
    review_rate_limit_per_hour: int = 10
    training_rate_limit_per_minute: int = 60
    # Shared hosted-engine daily pot (stockfishapi.com free tier is 2,000
    # units/day for the whole account). The guard trips before upstream does;
    # 0 disables it. Only ever consulted on the cloud route (D7 local-first).
    cloud_daily_unit_budget: int = 1800
    # Password reset (SEC): short-lived single-use tokens. `reset_link_base`
    # is the public web origin used to build the emailed link. SMTP is
    # optional — with no `smtp_host` the link is logged (dev convenience).
    password_reset_ttl_minutes: int = 60
    reset_link_base: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Google Sign-In (WEB auth): OAuth 2.0 client ID verified server-side.
    # Empty = Google sign-in disabled; never commit a real value.
    google_client_id: str = ""
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
    # Coach assistant (Phase 11). The LLM is OPTIONAL and env-gated: with no
    # `assistant_api_key` the assistant answers deterministically from engine +
    # book facts (the offline test/CI default). The key is never committed,
    # logged, or returned. Recall depth and the per-user ask budget live here.
    assistant_api_key: str = ""
    assistant_base_url: str = "https://api.openai.com/v1"
    assistant_model: str = "gpt-4o-mini"
    assistant_max_tokens: int = 400
    assistant_rate_limit_per_minute: int = 20
    coach_recall_top_k: int = 6
    coach_patterns_min: int = 2
    # Conversational coach upgrade (Phase 11b): how much recent thread is sent
    # back for follow-up resolution/LLM context, and how long a walkable board
    # line may get before it is truncated. Both only bound size — never content.
    coach_history_max_turns: int = 8
    coach_line_max_steps: int = 8
    log_level: str = "INFO"
    # ElevenLabs TTS proxy (optional; free tier = 10k chars/month). Empty key
    # means the browser's speechSynthesis fallback is used instead. Never
    # commit a real key — the API endpoint is server-side only (the browser
    # never sees this value). Default voice/model are among the free-tier
    # premium voices; swap via ELEVENLABS_VOICE_ID / ELEVENLABS_MODEL_ID.
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Adam (free-tier API accessible)
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    # MON-001: JSON lines are the default; false restores the text format.
    log_json: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

if settings.app_env == "production" and settings.secret_key == "change-me-in-development-only":
    raise RuntimeError("REFUSE TO START: set a unique SECRET_KEY in production (REL-002).")

# Structured logging (REL-008, MON-001): one record per line to stdout —
# JSON objects by default, text lines when LOG_JSON=false. Levels and format
# live in app/core/telemetry.py; nothing here logs secrets or session tokens.
telemetry.configure_logging(settings.log_level, settings.log_json)
logger = logging.getLogger("chess-engine-api")


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Create engine
engine = create_engine(settings.database_url, echo=False)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
