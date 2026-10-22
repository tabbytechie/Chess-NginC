"""atomic game constraints

Revision ID: a1b2c3d4e5f6
Revises: 5a0dcdb13bb3
Create Date: 2026-10-11 09:20:00.000000

Makes persisted game state impossible to corrupt:

* ``UNIQUE (game_id, move_number)`` — two concurrent plies can no longer both
  claim the same slot in a game's history.
* ``ON DELETE CASCADE`` on the owning rows — deleting a user or a game cannot
  leave orphan sessions, moves, or engine runs behind.
* ``CHECK`` on ``games.status`` / ``games.mode`` — the domain enums are now
  enforced by the database, not only by Python.
* ``timestamptz`` everywhere — stored instants stop depending on the server's
  zone, matching the aware ``utc_now()`` defaults in the models.

Pre-launch, so the constraint additions run against fresh data; the timestamp
conversion is expressed explicitly rather than via ``USING`` so the downgrade is
reversible without a cast ambiguity.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "5a0dcdb13bb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column) pairs that stored naive UTC and become timestamptz.
_TIMESTAMP_COLUMNS: tuple[tuple[str, str], ...] = (
    ("users", "created_at"),
    ("games", "created_at"),
    ("games", "updated_at"),
    ("sessions", "created_at"),
    ("sessions", "expires_at"),
    ("engine_runs", "created_at"),
    ("game_moves", "created_at"),
    ("benchmark_runs", "created_at"),
    ("benchmark_results", "created_at"),
)

_STATUS_VALUES = ("active", "checkmate", "stalemate", "draw", "resigned", "abandoned")
_MODE_VALUES = ("local", "computer")


def _to_timestamptz(table: str, column: str) -> None:
    """Reinterpret an existing naive value as UTC, not as the server's local time."""
    op.alter_column(
        table,
        column,
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_type=postgresql.TIMESTAMP(timezone=False),
        existing_nullable=False,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def _to_timestamp(table: str, column: str) -> None:
    """Downgrade: render the instant back to a naive UTC value."""
    op.alter_column(
        table,
        column,
        type_=postgresql.TIMESTAMP(timezone=False),
        existing_type=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    """Upgrade schema."""
    # Refuse to add the uniqueness the history depends on if it is already
    # violated, instead of silently picking one of the duplicate plies.
    duplicate_plys = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM game_moves GROUP BY game_id, move_number HAVING count(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate_plys is not None:
        raise RuntimeError(
            "game_moves contains duplicate (game_id, move_number) rows; "
            "de-duplicate the history before applying this migration."
        )

    for table, column in _TIMESTAMP_COLUMNS:
        _to_timestamptz(table, column)

    op.create_unique_constraint(
        "uq_game_moves_game_move_number", "game_moves", ["game_id", "move_number"]
    )

    op.create_check_constraint(
        "ck_games_status", "games", f"status IN ({', '.join(repr(v) for v in _STATUS_VALUES)})"
    )
    op.create_check_constraint(
        "ck_games_mode", "games", f"mode IN ({', '.join(repr(v) for v in _MODE_VALUES)})"
    )

    # Named FKs with cascade: the unnamed originals were created implicitly and
    # are dropped by their Postgres-generated names.
    op.drop_constraint("games_user_id_fkey", "games", type_="foreignkey")
    op.create_foreign_key(
        "fk_games_user_id", "games", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("sessions_user_id_fkey", "sessions", type_="foreignkey")
    op.create_foreign_key(
        "fk_sessions_user_id", "sessions", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("engine_runs_game_id_fkey", "engine_runs", type_="foreignkey")
    op.create_foreign_key(
        "fk_engine_runs_game_id", "engine_runs", "games", ["game_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("game_moves_game_id_fkey", "game_moves", type_="foreignkey")
    op.create_foreign_key(
        "fk_game_moves_game_id", "game_moves", "games", ["game_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_game_moves_game_id", "game_moves", type_="foreignkey")
    op.create_foreign_key("game_moves_game_id_fkey", "game_moves", "games", ["game_id"], ["id"])
    op.drop_constraint("fk_engine_runs_game_id", "engine_runs", type_="foreignkey")
    op.create_foreign_key("engine_runs_game_id_fkey", "engine_runs", "games", ["game_id"], ["id"])
    op.drop_constraint("fk_sessions_user_id", "sessions", type_="foreignkey")
    op.create_foreign_key("sessions_user_id_fkey", "sessions", "users", ["user_id"], ["id"])
    op.drop_constraint("fk_games_user_id", "games", type_="foreignkey")
    op.create_foreign_key("games_user_id_fkey", "games", "users", ["user_id"], ["id"])

    op.drop_constraint("ck_games_mode", "games", type_="check")
    op.drop_constraint("ck_games_status", "games", type_="check")
    op.drop_constraint("uq_game_moves_game_move_number", "game_moves", type_="unique")

    for table, column in reversed(_TIMESTAMP_COLUMNS):
        _to_timestamp(table, column)
