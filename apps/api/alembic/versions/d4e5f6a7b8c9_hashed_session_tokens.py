"""hashed session tokens: store a digest, never the raw bearer token

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-03 09:00:00.000000

The ``sessions`` table used to store the raw session token, so any read of the
database (a leak, a backup, a support query) handed over live cookies. This
replaces it with ``token_hash`` — a SHA-256 digest of the token — which is
irreversible and cannot be replayed as a cookie (SEC-021).

The digest cannot be derived from the existing plaintext in a way that preserves
sessions for the running app (the app now hashes before lookup, and old rows have
no hash), and this is pre-launch, so every session is dropped: users log in once
more. That forced logout is recorded in ADR-008.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Invalidate all outstanding sessions (ADR-008: accepted forced re-login).
    op.execute("TRUNCATE TABLE sessions RESTART IDENTITY")
    op.drop_index(op.f("ix_sessions_token"), table_name="sessions", if_exists=True)
    op.drop_column("sessions", "token")
    op.add_column("sessions", sa.Column("token_hash", sa.String(length=64), nullable=False))
    op.create_index(op.f("ix_sessions_token_hash"), "sessions", ["token_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_sessions_token_hash"), table_name="sessions", if_exists=True)
    op.drop_column("sessions", "token_hash")
    op.execute("TRUNCATE TABLE sessions RESTART IDENTITY")
    op.add_column("sessions", sa.Column("token", sa.String(length=255), nullable=False))
    op.create_index(op.f("ix_sessions_token"), "sessions", ["token"], unique=True)
