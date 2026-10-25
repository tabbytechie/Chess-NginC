"""User model for authentication."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """User account for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Nullable: Google-only accounts have no password until they set one via
    # the reset flow.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Running total of the point ledger (see PointAward); chess.com-style.
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Voice (AI coach narration): the user must opt in before the assistant
    # speaks an answer aloud (consent gate), and the chosen voice is either a
    # curated free-tier ElevenLabs id (validated against the allowlist on write)
    # or empty, meaning the browser's own speech engine. Server-side so the
    # choice follows the account across devices.
    voice_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
