"""Threefold repetition through the API (CHS-014).

The defect these tests pin down: a status check built on `ChessRules(game.fen)`
has no move history, so python-chess can *never* see a repetition and a game can
reach a drawn position without the API acknowledging it. Status must be derived
by replaying the persisted UCI moves.
"""

import pytest
from fastapi.testclient import TestClient

from app.games.domain import STARTING_FEN
from app.games.rules import ChessRules

# Ng1-f3 / Ng8-f6 / Nf3-g1 / Ng8-f6 repeated: every return of the knights to
# their developed squares re-creates an earlier position with the same side to
# move, so the third occurrence lands on ply 7 and the fourth on ply 8.
REPETITION_PLYS = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8"]


def _create(client: TestClient, mode: str = "local") -> dict:
    resp = client.post("/api/v1/games", json={"mode": mode})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _play(client: TestClient, game_id: int, plys: list[str]) -> dict:
    """Play a legal sequence, tracking the version chain like a real client."""
    version = 1
    body: dict = {}
    for index, uci in enumerate(plys, start=1):
        resp = client.post(
            f"/api/v1/games/{game_id}/moves", json={"uci": uci, "expected_version": version}
        )
        assert resp.status_code == 200, (index, uci, resp.text)
        body = resp.json()
        version = body["version"]
    return body


def test_fen_alone_cannot_see_the_repetition() -> None:
    """The premise: the same position read from FEN looks alive."""
    replayed = ChessRules.from_moves(REPETITION_PLYS, STARTING_FEN)
    fen_only = ChessRules(replayed.fen)
    assert replayed.is_repetition(3) is True
    assert fen_only.is_repetition(3) is False
    assert fen_only.status().value == "active"


@pytest.mark.parametrize(
    ("plies", "expected"),
    [
        (4, "active"),  # second occurrence of the developed position
        (5, "active"),
        (6, "active"),  # still only two occurrences with black to move
        (7, "draw"),  # third occurrence: the API must say so
    ],
)
def test_repetition_is_reported_by_the_api(
    authed_client: tuple[TestClient, dict], plies: int, expected: str
) -> None:
    """Status comes from the replayed history, at the ply the rules say."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], REPETITION_PLYS[:plies])
    played = REPETITION_PLYS[:plies]
    assert body["fen"] == ChessRules.from_moves(played, STARTING_FEN).fen
    assert body["status"] == expected, (played, body)
    assert len(body["moves"]) == plies


def test_moves_are_rejected_once_repetition_ends_the_game(
    authed_client: tuple[TestClient, dict],
) -> None:
    """A repetition draw is terminal through the API, not just advisory."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], REPETITION_PLYS[:7])
    assert body["status"] == "draw"
    refused = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": body["version"]},
    )
    assert refused.status_code == 409
    # The rejected move left nothing behind.
    after = client.get(f"/api/v1/games/{game['id']}").json()
    assert len(after["moves"]) == 7
    assert after["version"] == body["version"]


def test_undo_restores_the_repetition_context(
    authed_client: tuple[TestClient, dict],
) -> None:
    """Undo replays the surviving history, so the restored position stays exact."""
    client, _ = authed_client
    game = _create(client)
    body = _play(client, game["id"], REPETITION_PLYS[:7])
    assert body["status"] == "draw"
    # Undo refuses a finished game: repetition must not open a way back.
    refused = client.post(
        f"/api/v1/games/{game['id']}/undo", json={"expected_version": body["version"]}
    )
    assert refused.status_code == 409

    live = _create(client)
    played = _play(client, live["id"], ["e2e4", "e7e5", "g1f3"])
    undone = client.post(
        f"/api/v1/games/{live['id']}/undo", json={"expected_version": played["version"]}
    )
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["fen"] == ChessRules.from_moves(["e2e4", "e7e5"], STARTING_FEN).fen
    assert [m["uci"] for m in body["moves"]] == ["e2e4", "e7e5"]


def test_draw_claim_still_rejected_without_a_drawn_position(
    authed_client: tuple[TestClient, dict],
) -> None:
    """Replaying history must not make every claim valid."""
    client, _ = authed_client
    game = _create(client)
    _play(client, game["id"], ["e2e4", "e7e5", "g1f3"])
    assert client.post(f"/api/v1/games/{game['id']}/draw-claim").status_code == 422
