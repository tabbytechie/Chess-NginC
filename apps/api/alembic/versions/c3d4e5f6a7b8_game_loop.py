"""game loop: side, difficulty, and result attribution

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-11-02 10:15:00.000000

Turns the persisted game into a real human-vs-engine game by recording:

* ``player_color`` — which side the human plays (``white``/``black``), so a
  computer game can enforce whose turn it is and orient the board.
* ``engine_level`` — the bot difficulty (``easy``/``medium``/``hard``), which the
  service maps to a bounded search budget (ADR-010).
* ``end_reason`` / ``winner`` / ``result`` — how a finished game ended and the
  standard PGN result token, so outcomes are attributable instead of only a
  status string.

Pre-launch: new columns carry server defaults so existing rows are backfilled to
a sensible white-to-move, open game; the defaults are dropped afterwards so the
values live in Python (the model defaults) rather than leaking into the schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column("player_color", sa.String(length=5), nullable=False, server_default="white"),
    )
    op.add_column(
        "games",
        sa.Column("engine_level", sa.String(length=12), nullable=False, server_default="medium"),
    )
    op.add_column("games", sa.Column("end_reason", sa.String(length=16), nullable=True))
    op.add_column("games", sa.Column("winner", sa.String(length=5), nullable=True))
    op.add_column(
        "games", sa.Column("result", sa.String(length=8), nullable=False, server_default="*")
    )

    # Drop the server defaults: the model supplies them, and a schema default
    # would silently paper over a missing value in application code.
    op.alter_column("games", "player_color", server_default=None)
    op.alter_column("games", "engine_level", server_default=None)
    op.alter_column("games", "result", server_default=None)

    op.create_check_constraint(
        "ck_games_player_color", "games", "player_color IN ('white', 'black')"
    )
    op.create_check_constraint(
        "ck_games_engine_level", "games", "engine_level IN ('easy', 'medium', 'hard')"
    )
    # Nullable CHECKs pass on NULL, so active games without a result are valid.
    op.create_check_constraint(
        "ck_games_end_reason",
        "games",
        "end_reason IN ('checkmate', 'stalemate', 'draw', 'resignation', 'abandoned')",
    )
    op.create_check_constraint("ck_games_winner", "games", "winner IN ('white', 'black')")
    op.create_check_constraint(
        "ck_games_result", "games", "result IN ('1-0', '0-1', '1/2-1/2', '*')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_games_result", "games", type_="check")
    op.drop_constraint("ck_games_winner", "games", type_="check")
    op.drop_constraint("ck_games_end_reason", "games", type_="check")
    op.drop_constraint("ck_games_engine_level", "games", type_="check")
    op.drop_constraint("ck_games_player_color", "games", type_="check")

    op.drop_column("games", "result")
    op.drop_column("games", "winner")
    op.drop_column("games", "end_reason")
    op.drop_column("games", "engine_level")
    op.drop_column("games", "player_color")
