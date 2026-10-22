"""Auth token model for email verification and password reset (single-use)."""

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


def _quoted_values(enum_cls: Iterable[StrEnum]) -> str:
    """`'a', 'b', ...` for a CHECK constraint, kept in sync with the domain enum."""
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class TokenPurpose(StrEnum):
    """What a recovery token is valid for; never interchangeable."""

    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class AuthToken(Base):
    """A hashed, purpose-scoped, single-use account-recovery token."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        CheckConstraint(
            f"purpose IN ({_quoted_values(TokenPurpose)})",
            name="ck_auth_tokens_purpose",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_auth_tokens_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
