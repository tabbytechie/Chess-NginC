"""HTTP request/response schemas for API v1 (SEC-016: safe error shapes)."""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    """Login payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class EmailRequest(BaseModel):
    """An email address for a recovery request (verification resend / reset)."""

    email: str = Field(max_length=255)


class VerifyEmailRequest(BaseModel):
    """Email-verification token submitted from the link."""

    token: str = Field(min_length=1, max_length=256)


class ResetPasswordRequest(BaseModel):
    """Password-reset token plus the new password."""

    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class RecoveryMessageResponse(BaseModel):
    """Uniform, non-enumerating reply for a recovery request."""

    detail: str


class UserResponse(BaseModel):
    """Public user representation (never includes password hash)."""

    id: int
    email: str
    email_verified: bool


class ErrorResponse(BaseModel):
    """Consistent error envelope (SEC-016)."""

    detail: str


class ReadinessResponse(BaseModel):
    """Readiness probe result (REL-007).

    ``engine`` reports the opponent backend (``builtin``/``local``/``up``/
    ``degraded``); it is informational and never makes the endpoint non-ready.
    """

    status: str
    database: str
    engine: str


class CreateGameRequest(BaseModel):
    """Game creation payload (API-005).

    ``player_color`` and ``engine_level`` are the new-game choices for a
    computer game; they are persisted on the row and drive whose turn is
    enforced and how hard the engine searches. ``random`` resolves server-side to
    a coin flip at the route before the row is written.
    """

    mode: str = Field(default="local", max_length=50)
    player_color: str = Field(default="white", max_length=6)
    engine_level: str = Field(default="medium", max_length=12)


class MoveRequest(BaseModel):
    """Move submission payload (API-008/019)."""

    uci: str = Field(min_length=4, max_length=10)
    expected_version: int = Field(ge=1)


class VersionRequest(BaseModel):
    """Payload for version-guarded actions (API-009/012)."""

    expected_version: int = Field(ge=1)


class EngineMoveRequest(BaseModel):
    """Engine move payload (API-012).

    Depth and time are no longer client-settable: the opponent's strength comes
    from the game's difficulty (Phase 3), which the server maps to a bounded
    search budget. The client only supplies the version it is playing against.
    """

    expected_version: int = Field(ge=1)


class MoveResponse(BaseModel):
    """A stored move."""

    uci: str
    san: str
    move_number: int


class GameResponse(BaseModel):
    """A game with its move history (API-006/007)."""

    id: int
    mode: str
    status: str
    fen: str
    version: int
    player_color: str
    engine_level: str
    result: str
    winner: str | None = None
    end_reason: str | None = None
    # Always present in every response the route builds, so they are required
    # (no defaults) — the OpenAPI contract then emits them as definite fields
    # rather than optional, which the generated frontend types rely on.
    in_check: bool
    move_count: int
    moves: list[MoveResponse]


class GameSummaryResponse(BaseModel):
    """A listable row from ``GET /games`` — no move payloads (API-006)."""

    id: int
    mode: str
    status: str
    player_color: str
    engine_level: str
    result: str
    winner: str | None = None
    version: int
    move_count: int
    last_played_at: str


class GameListResponse(BaseModel):
    """A page of summaries plus the total, so the client can paginate."""

    items: list[GameSummaryResponse]
    total: int
    limit: int
    offset: int


class ModeStats(BaseModel):
    """Wins/losses/draws for one game mode."""

    # Every aggregate row carries all five counts, so they are required.
    wins: int
    losses: int
    draws: int
    finished: int
    total: int


class StatsResponse(BaseModel):
    """Aggregate record keyed by mode (API-021)."""

    by_mode: dict[str, ModeStats]
