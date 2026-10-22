"""Games endpoints: CRUD + moves + resign/draw/engine (API-005..012)."""

import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import (
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_engine,
    rate_limit_writes,
)
from app.engine.errors import EngineSaturatedError, EngineUnavailableError
from app.games import service as game_service
from app.games.domain import Color
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    GameSummary,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.user import User

from .schemas import (
    CreateGameRequest,
    EngineMoveRequest,
    ErrorResponse,
    GameListResponse,
    GameResponse,
    GameSummaryResponse,
    ModeStats,
    MoveRequest,
    MoveResponse,
    StatsResponse,
    VersionRequest,
)

router = APIRouter(tags=["games"])

# Module-level dependency singletons (E402 exempted; see auth.py).
_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402
_RateLimitWrites = Depends(rate_limit_writes)  # noqa: E402
_RateLimitEngine = Depends(rate_limit_engine)  # noqa: E402


def _to_response(detail: GameDetail) -> GameResponse:
    game = detail.game
    return GameResponse(
        id=game.id,
        mode=game.mode,
        status=game.status,
        fen=game.fen,
        version=game.version,
        player_color=game.player_color,
        engine_level=game.engine_level,
        result=game.result,
        winner=game.winner,
        end_reason=game.end_reason,
        in_check=detail.in_check,
        move_count=len(detail.moves),
        moves=[MoveResponse(uci=m.uci, san=m.san, move_number=m.move_number) for m in detail.moves],
    )


def _to_summary(summary: GameSummary) -> GameSummaryResponse:
    return GameSummaryResponse(
        id=summary.id,
        mode=summary.mode,
        status=summary.status,
        player_color=summary.player_color,
        engine_level=summary.engine_level,
        result=summary.result,
        winner=summary.winner,
        version=summary.version,
        move_count=summary.move_count,
        last_played_at=summary.last_played_at.isoformat(),
    )


def _map_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (StaleVersionError, GameFinishedError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, IllegalMoveRequestError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, EngineSaturatedError):
        # Every engine slot is busy; ask the client to back off briefly.
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine is busy, please retry shortly",
            headers={"Retry-After": "2"},
        )
    if isinstance(exc, EngineUnavailableError):
        # Escapes only if even the custom fallback failed; never a silent 500.
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine temporarily unavailable",
            headers={"Retry-After": "2"},
        )
    raise exc  # pragma: no cover - unexpected


@router.post(
    "/games",
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    dependencies=[_SameOrigin, _RateLimitWrites],
)
def create_game(
    payload: CreateGameRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Create a game in the starting position (API-005).

    ``random`` colour is resolved here so the persisted row records a concrete
    side; a computer game where the player draws Black returns with the engine's
    opening already played.
    """
    player_color = payload.player_color
    if player_color == "random":
        player_color = random.choice((Color.WHITE.value, Color.BLACK.value))  # noqa: S311
    try:
        detail = game_service.create_game(
            db, current_user.id, payload.mode, player_color, payload.engine_level
        )
    except IllegalMoveRequestError as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.get("/games", response_model=GameListResponse)
def list_games(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
    status_filter: Annotated[str | None, Query(alias="status", max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GameListResponse:
    """List the caller's games as a bounded page of summaries (API-006).

    One aggregate query, no per-row move fetches: this replaces the N+1 that
    used to call ``get_game`` for every row.
    """
    summaries, total = game_service.list_game_summaries(
        db, current_user.id, status=status_filter, limit=limit, offset=offset
    )
    return GameListResponse(
        items=[_to_summary(s) for s in summaries], total=total, limit=limit, offset=offset
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> StatsResponse:
    """Aggregate wins/losses/draws by mode, from one query (API-021)."""
    raw = game_service.compute_stats(db, current_user.id)
    return StatsResponse(by_mode={mode: ModeStats(**counts) for mode, counts in raw.items()})


@router.get(
    "/games/{game_id}",
    response_model=GameResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Fetch one game; 404 for unknown or foreign games (API-007)."""
    try:
        return _to_response(game_service.get_game(db, game_id, current_user.id))
    except GameNotFoundError as exc:
        raise _map_errors(exc) from None


@router.get(
    "/games/{game_id}/pgn",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def export_pgn(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> Response:
    """Download the game as PGN text (API-020).

    Returns ``text/plain`` with an attachment disposition so browsers save it as
    ``game-<id>.pgn`` rather than rendering it.
    """
    try:
        body = game_service.get_pgn(db, game_id, current_user.id)
    except GameNotFoundError as exc:
        raise _map_errors(exc) from None
    return Response(
        content=body,
        media_type="application/x-chess-pgn",
        headers={"Content-Disposition": f'attachment; filename="game-{game_id}.pgn"'},
    )


_MOVE_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/games/{game_id}/moves",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin, _RateLimitWrites],
)
def submit_move(
    game_id: int,
    payload: MoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Validate + persist a UCI move (API-008/018/019)."""
    try:
        detail = game_service.submit_move(
            db, game_id, current_user.id, payload.uci, payload.expected_version
        )
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/undo",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin, _RateLimitWrites],
)
def undo_move(
    game_id: int,
    payload: VersionRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Undo the last move (API-009)."""
    try:
        detail = game_service.undo_move(db, game_id, current_user.id, payload.expected_version)
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/resign",
    response_model=GameResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    dependencies=[_SameOrigin, _RateLimitWrites],
)
def resign_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Resign an active game (API-010)."""
    try:
        detail = game_service.resign_game(db, game_id, current_user.id)
    except (GameNotFoundError, GameFinishedError) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/draw-claim",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin, _RateLimitWrites],
)
def claim_draw(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Claim a draw when the position supports it (API-011)."""
    try:
        detail = game_service.claim_draw(db, game_id, current_user.id)
    except (
        GameNotFoundError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/engine-move",
    response_model=GameResponse,
    responses={**_MOVE_RESPONSES, 503: {"model": ErrorResponse}},
    dependencies=[_SameOrigin, _RateLimitEngine],
)
def engine_move(
    game_id: int,
    payload: EngineMoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Ask the configured engine to play one ply (API-012).

    Strength is no longer client-controlled; the server maps the game's
    difficulty to a bounded budget and falls back to the custom engine if the
    primary backend is unavailable, so this never returns a silent 500.
    """
    try:
        detail = game_service.request_engine_move(
            db,
            game_id,
            current_user.id,
            payload.expected_version,
        )
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
        EngineSaturatedError,
        EngineUnavailableError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)
