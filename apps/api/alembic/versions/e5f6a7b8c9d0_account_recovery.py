"""account recovery: email verification + password-reset tokens

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-03 09:30:00.000000

Adds the account-state and token storage behind email verification and password
reset (SEC-013):

* ``users.email_verified`` / ``users.verified_at`` — whether the address has been
  confirmed and when. New accounts start unverified; the value is a plain flag,
  not a secret.
* ``auth_tokens`` — single-use, purpose-scoped recovery tokens. Only a keyed
  digest is stored (never the emailed secret), tokens carry an expiry, and a
  ``consumed_at`` stamp makes each usable exactly once. ``user_id`` cascades so
  deleting an account removes its tokens.

Pre-launch: ``email_verified`` defaults to false for every existing row, which is
the honest state (no verification existed before).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    # Default lives in the model, not the schema.
    op.alter_column("users", "email_verified", server_default=None)

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_tokens_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')", name="ck_auth_tokens_purpose"
        ),
    )
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_auth_tokens_token_hash"), "auth_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_auth_tokens_token_hash"), table_name="auth_tokens", if_exists=True)
    op.drop_index(op.f("ix_auth_tokens_user_id"), table_name="auth_tokens", if_exists=True)
    op.drop_table("auth_tokens")
    op.drop_column("users", "verified_at")
    op.drop_column("users", "email_verified")
