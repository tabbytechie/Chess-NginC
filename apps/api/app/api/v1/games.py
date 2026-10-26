"""Games endpoints: CRUD + moves + resign/draw/engine (API-005..012)."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.v1.achievements import celebrate, celebrate_at_end
from app.api.v1.deps import (
    check_review_rate,
    enforce_same_origin,
    get_current_user,
    get_db_session,
)
from app.api.v1.serializers import as_http_exception, to_game_response, to_review_response
from app.games import service as game_service
from app.games.errors import EngineUnavailableError
from app.games.service import (
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.user import User
from app.reviews import service as review_service
from app.reviews.service import ReviewTargetError

from .schemas import (
    CreateGameRequest,
    EngineMoveRequest,
    ErrorResponse,
    GameResponse,
    MoveRequest,
    ReviewRequest,
    ReviewResponse,
    VersionRequest,
)

router = APIRouter(tags=["games"])

# Module-level dependency singletons (E402 exempted; see auth.py).
_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402


def _to_response(detail: game_service.GameDetail) -> GameResponse:
    return to_game_response(detail)


def _mutation_response(db: Session, detail: game_service.GameDetail, user_id: int) -> GameResponse:
    """A mutation that ended a game carries its fresh unlocks (ACH-006)."""
    return to_game_response(detail, celebrate_at_end(db, detail, user_id))


def _map_errors(exc: Exception) -> HTTPException:
    return as_http_exception(exc)


@router.post(
    "/games",
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def create_game(
    payload: CreateGameRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Create a game in the starting position (API-005)."""
    try:
        game = game_service.create_game(db, current_user.id, payload.mode)
    except IllegalMoveRequestError as exc:
        raise _map_errors(exc) from None
    detail = game_service.get_game(db, game.id, current_user.id)
    # Starting a game changes the counting stats (games/modes), so evaluate here;
    # celebrating on the very first click is the point of the feature.
    return to_game_response(detail, celebrate(db, current_user.id))


@router.get("/games", response_model=list[GameResponse])
def list_games(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> list[GameResponse]:
    """List the caller's games (API-006)."""
    games = game_service.list_games(db, current_user.id)
    return [_to_response(game_service.get_game(db, g.id, current_user.id)) for g in games]


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


_MOVE_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}

# Engine moves can additionally fail with the Stockfish opponent down (PLAY-003).
_ENGINE_MOVE_RESPONSES: dict[int | str, dict[str, object]] = {
    **_MOVE_RESPONSES,
    503: {"model": ErrorResponse},
}


@router.post(
    "/games/{game_id}/moves",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
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
    return _mutation_response(db, detail, current_user.id)


@router.post(
    "/games/{game_id}/undo",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
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
    dependencies=[_SameOrigin],
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
    return _mutation_response(db, detail, current_user.id)


@router.post(
    "/games/{game_id}/draw-claim",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
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
    return _mutation_response(db, detail, current_user.id)


@router.post(
    "/games/{game_id}/engine-move",
    response_model=GameResponse,
    responses=_ENGINE_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def engine_move(
    game_id: int,
    payload: EngineMoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Ask real Stockfish for a move within budget (API-012, SEC-013, PLAY-001)."""
    try:
        detail = game_service.request_engine_move(
            db,
            game_id,
            current_user.id,
            payload.expected_version,
            max_depth=payload.max_depth,
            max_time_ms=payload.max_time_ms,
        )
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
        EngineUnavailableError,
    ) as exc:
        raise _map_errors(exc) from None
    return _mutation_response(db, detail, current_user.id)


_REVIEW_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


# RB-005: the GET validator is a digest of the exact bytes served, so it is
# structurally impossible to go stale — it changes the moment a force re-run
# rewrites the payload *or* a deploy shifts a read-time annotation. There is no
# in-process memo: recomputing an md5 over a body already serialized for the
# response is negligible, and a memo would leak one worker's view to another
# the day the API runs with more than one process.
def _review_etag(body: str) -> str:
    """Content digest of the served review body, as an HTTP validator value.

    MD5 here is a cache validator, not a security boundary.
    """
    return hashlib.md5(body.encode()).hexdigest()


@router.post(
    "/games/{game_id}/review",
    response_model=ReviewResponse,
    responses={**_REVIEW_RESPONSES, 429: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def create_game_review(
    game_id: int,
    payload: ReviewRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> ReviewResponse:
    """Generate (or return the cached) engine review of a finished game (REVIEW-001)."""
    # A generation holds a warm engine for seconds of CPU (TD-013), so the POST
    # is budgeted per hour and a force pays double (RL-001/D15). The cached GET
    # path above stays free — players re-reading their review costs nothing.
    check_review_rate(current_user.id, force=payload.force)
    try:
        review = review_service.generate_or_get(db, game_id, current_user.id, force=payload.force)
    except (GameNotFoundError, ReviewTargetError) as exc:
        raise _map_errors(exc) from None
    # Reviewing games is its own achievement track, so a finished analysis is
    # worth an evaluation even though no game state changed.
    unlocked = celebrate(db, current_user.id) if review.status == "completed" else []
    return to_review_response(review, unlocked)


@router.get(
    "/games/{game_id}/review",
    response_model=ReviewResponse,
    responses={**_REVIEW_RESPONSES, 409: {"model": ErrorResponse}},
)
def get_game_review(
    game_id: int,
    request: Request,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> ReviewResponse | Response:
    """Return the caller's stored review without re-running the engine (REVIEW-005).

    RB-005: the response carries a content ETag, so a conditional GET on an
    unchanged review answers 304 and skips sending the (possibly large) JSON
    over the wire. `private, no-cache` keeps shared caches off a per-user body
    while allowing browser revalidation.
    """
    try:
        # Access check shared with POST: unknown/foreign games → 404.
        review_service.load_game(db, game_id, current_user.id)
        review = review_service.get_existing(db, game_id, current_user.id)
    except GameNotFoundError as exc:
        raise _map_errors(exc) from None
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No review exists yet for this game",
        )
    # Serialize once, then digest the exact bytes served so the validator can
    # never drift from the body — read-time annotations included (RB-005).
    body = to_review_response(review).model_dump_json()
    etag = f'"{_review_etag(body)}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, no-cache"},
    )
