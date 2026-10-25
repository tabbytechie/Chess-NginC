"""Voice preferences on the user: AI-coach narration consent + selected voice.

Revision ID: b4e2d7c0a915
Revises: f6b1c8d2a9e4
Create Date: 2026-10-25

Server-side so the choice follows the account across devices. The consent flag
gates whether the assistant may speak an answer aloud; the voice id is either a
curated free-tier ElevenLabs id or empty (browser engine). Written with a
server default so existing rows backfill, then the default is dropped so the
schema matches the ORM's python-side default (keeps `alembic check` clean).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e2d7c0a915"
down_revision: str | Sequence[str] | None = "f6b1c8d2a9e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("voice_authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("voice_id", sa.String(length=64), nullable=False, server_default=""),
    )
    # Match the ORM: defaults are applied in Python, not the schema.
    op.alter_column("users", "voice_authorized", server_default=None)
    op.alter_column("users", "voice_id", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "voice_id")
    op.drop_column("users", "voice_authorized")
