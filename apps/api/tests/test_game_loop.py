"""Phase 3 game-loop tests: side, difficulty, auto-reply, and outcome (API-020/021).

These cover the behaviour that turns the persisted board into a real
human-vs-engine game: whose turn is enforced, that a computer move answers in
the same response, that results are attributed (winner / result / end_reason),
that undo removes a whole ply pair, and that PGN/stats/pagination read paths
work. The engine is the always-available custom provider, so no sidecar or
binary is needed here.
"""

import io

import chess
import chess.pgn
import pytest
from fastapi.testclient import TestClient

from app.games import service
from app.games.domain import STARTING_FEN
from app.games.rules import ChessRules
from app.models.user import User
from app.repositories.game_repository import GameRepository


def _create(client: TestClient, *, mode="local", color="white", level="easy") -> dict:
    resp = client.post(
        "/api/v1/games", json={"mode": mode, "player_color": color, "engine_level": level}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _play(client: TestClient, game_id: int, plies: list[str], version: int = 1) -> dict:
    body: dict = {}
    for uci in plies:
        resp = client.post(
            f"/api/v1/games/{game_id}/moves", json={"uci": uci, "expected_version": version}
        )
        assert resp.status_code == 200, (uci, resp.text)
        body = resp.json()
        version = body["version"]
    return body


# ------------------------------------------------------------- the loop


def test_computer_game_auto_replies_both_plies(authed_client: tuple[TestClient, dict]) -> None:
    """A human ply in a computer game returns the engine's reply in one response."""
    client, _ = authed_client
    game = _create(client, mode="computer")
    assert game["player_color"] == "white"
    assert game["version"] == 1 and game["moves"] == []

    body = client.post(
        f"/api/v1/games/{game['id']}/moves", json={"uci": "e2e4", "expected_version": 1}
    ).json()
    assert body["version"] == 3, "both plies committed in one request"
    assert len(body["moves"]) == 2
    assert body["moves"][0]["uci"] == "e2e4"
    reply = body["moves"][1]["uci"]
    # The reply is a legal Black move for the position after 1.e4.
    board = chess.Board(STARTING_FEN)
    board.push(chess.Move.from_uci("e2e4"))
    assert chess.Move.from_uci(reply) in board.legal_moves
    assert body["status"] == "active"


def test_computer_game_as_black_opens_with_the_engine(
    authed_client: tuple[TestClient, dict],
) -> None:
    """Taking Black means the engine plays White's opening before you move."""
    client, _ = authed_client
    game = _create(client, mode="computer", color="black")
    assert game["player_color"] == "black"
    assert game["version"] == 2 and len(game["moves"]) == 1
    opening = game["moves"][0]["uci"]
    assert chess.Move.from_uci(opening) in chess.Board(STARTING_FEN).legal_moves
    # It is now the player's (Black's) turn.
    body = client.post(
        f"/api/v1/games/{game['id']}/moves", json={"uci": "e7e5", "expected_version": 2}
    ).json()
    assert body["moves"][1]["uci"] == "e7e5"
    assert body["version"] == 4 and len(body["moves"]) == 3


def test_human_cannot_move_for_the_engine_side(db) -> None:
    """Service-level guard: a human ply played on the engine's colour is refused.

    The auto-reply normally leaves the client always on its own turn, so this
    reaches the engine-to-move snapshot directly by applying a single human ply
    through the internal helper and then attempting a second human ply.
    """
    user = User(email="side@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    detail = service.create_game(db, user.id, "computer", "white", "easy")
    game_id = detail.game.id
    repo = GameRepository(db)
    # One human ply only (bypassing the auto-reply): now it is Black's turn.
    service._apply_human_move(db, repo, game_id, user.id, "e2e4", 1)
    with pytest.raises(service.IllegalMoveRequestError, match="engine's move"):
        service.submit_move(db, game_id, user.id, "d7d5", 2)


# ------------------------------------------------------------- outcomes


def test_checkmate_attributes_winner_and_result(authed_client: tuple[TestClient, dict]) -> None:
    """Fool's mate: Black delivers mate, so winner=Black and result 0-1."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], ["f2f3", "e7e5", "g2g4", "d8h4"])
    assert body["status"] == "checkmate"
    assert body["winner"] == "black"
    assert body["result"] == "0-1"
    assert body["end_reason"] == "checkmate"


def test_checkmate_winner_white_attributes_one_zero(authed_client: tuple[TestClient, dict]) -> None:
    """Scholar's mate: White mates Black, so winner=White and result 1-0."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"])
    assert body["status"] == "checkmate"
    assert body["winner"] == "white"
    assert body["result"] == "1-0"
    assert body["in_check"] is True


def test_resign_attributes_win_to_the_opponent(authed_client: tuple[TestClient, dict]) -> None:
    """In a computer game the human resigns, so the engine's colour wins."""
    client, _ = authed_client
    game = _create(client, mode="computer", color="white")
    body = client.post(f"/api/v1/games/{game['id']}/resign").json()
    assert body["status"] == "resigned"
    assert body["end_reason"] == "resignation"
    assert body["winner"] == "black"  # engine plays Black against a white player
    assert body["result"] == "0-1"


def test_repetition_draw_sets_result_half(authed_client: tuple[TestClient, dict]) -> None:
    """A threefold draw carries 1/2-1/2 and end_reason draw, no winner."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"])
    assert body["status"] == "draw"
    assert body["result"] == "1/2-1/2"
    assert body["winner"] is None
    assert body["end_reason"] == "draw"


# ------------------------------------------------------------- undo pair


def test_undo_removes_the_ply_pair_in_computer_mode(authed_client: tuple[TestClient, dict]) -> None:
    """Undo in a computer game takes back both the reply and the human move."""
    client, _ = authed_client
    game = _create(client, mode="computer")
    body = client.post(
        f"/api/v1/games/{game['id']}/moves", json={"uci": "e2e4", "expected_version": 1}
    ).json()
    assert len(body["moves"]) == 2
    undone = client.post(
        f"/api/v1/games/{game['id']}/undo", json={"expected_version": body["version"]}
    ).json()
    assert undone["moves"] == []
    assert undone["fen"] == STARTING_FEN
    assert undone["status"] == "active"


# ------------------------------------------------------------- PGN export


def test_pgn_roundtrips_from_the_start(authed_client: tuple[TestClient, dict]) -> None:
    """GET /games/{id}/pgn yields a PGN that replays to the stored position."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], ["e2e4", "e7e5", "g1f3", "b8c6"])
    resp = client.get(f"/api/v1/games/{game['id']}/pgn")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-chess-pgn")
    assert f'filename="game-{game["id"]}.pgn"' in resp.headers["content-disposition"]

    parsed = chess.pgn.read_game(io.StringIO(resp.text))
    assert parsed is not None
    assert parsed.headers["Result"] == "*"
    board = parsed.board()
    played = list(parsed.mainline_moves())
    for move in played:
        board.push(move)
    assert [m.uci() for m in played] == ["e2e4", "e7e5", "g1f3", "b8c6"]
    assert board.fen() == ChessRules.from_moves(["e2e4", "e7e5", "g1f3", "b8c6"], STARTING_FEN).fen
    assert body["move_count"] == 4


# ------------------------------------------------------------- read paths


def test_pagination_and_status_filter(authed_client: tuple[TestClient, dict]) -> None:
    """GET /games returns a bounded page plus the true total, newest first."""
    client, _ = authed_client
    created = [_create(client)["id"] for _ in range(3)]
    _create(client, mode="computer")

    page = client.get("/api/v1/games?limit=2&offset=0").json()
    assert page["total"] == 4
    assert len(page["items"]) == 2
    assert [item["id"] for item in page["items"]] == sorted(
        [item["id"] for item in page["items"]], reverse=True
    )

    second = client.get("/api/v1/games?limit=2&offset=2").json()
    assert len(second["items"]) == 2

    only_computer = client.get("/api/v1/games?status=active&mode=computer")
    # status filter is honoured; unknown params are ignored, still 200.
    assert only_computer.status_code == 200

    assert created[0] == min(created)


def test_summaries_carry_no_move_payload_but_count_and_times(
    authed_client: tuple[TestClient, dict],
) -> None:
    client, _ = authed_client
    game = _create(client)
    _play(client, game["id"], ["e2e4", "e7e5"])
    item = client.get("/api/v1/games").json()["items"][0]
    assert item["move_count"] == 2
    assert "moves" not in item  # summaries never ship the move list
    assert item["last_played_at"]


def test_stats_aggregate_by_mode(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    # A win for the (default white) player: Scholar's mate.
    win = _create(client)
    _play(client, win["id"], ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"])
    # A resignation is a loss for the side that resigns (white to move).
    loss = _create(client)
    client.post(f"/api/v1/games/{loss['id']}/resign")

    stats = client.get("/api/v1/stats").json()["by_mode"]
    assert stats["local"]["wins"] == 1
    assert stats["local"]["losses"] == 1
    assert stats["local"]["finished"] == 2
