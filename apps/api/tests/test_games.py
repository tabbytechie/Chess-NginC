"""Games API integration tests (API-005..009, SEC-010/011/020)."""

from fastapi.testclient import TestClient

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _create(client: TestClient, mode: str = "local") -> dict:
    resp = client.post("/api/v1/games", json={"mode": mode})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_unauthenticated_games_rejected(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/v1/games", json={"mode": "local"}).status_code == 401
    assert client.get("/api/v1/games").status_code == 401
    assert client.get("/api/v1/games/1").status_code == 401


def test_create_list_get_game(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(client)
    assert game["fen"] == STARTING_FEN
    assert game["status"] == "active"
    assert game["version"] == 1
    assert game["moves"] == []

    listed = client.get("/api/v1/games")
    assert listed.status_code == 200
    payload = listed.json()
    assert [g["id"] for g in payload["items"]] == [game["id"]]
    assert payload["total"] == 1

    fetched = client.get(f"/api/v1/games/{game['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["fen"] == STARTING_FEN

    bad_mode = client.post("/api/v1/games", json={"mode": "chess960"})
    assert bad_mode.status_code == 422


def test_cross_account_isolation(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    client, _ = authed_client
    game = _create(client)
    assert other_client.get(f"/api/v1/games/{game['id']}").status_code == 404
    assert other_client.get("/api/v1/games").json()["items"] == []
    other_move = other_client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": 1},
    )
    assert other_move.status_code == 404


def test_submit_move_flow(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(client)
    gid = game["id"]

    r1 = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["version"] == 2
    assert body["moves"] == [{"uci": "e2e4", "san": "e4", "move_number": 1}]

    illegal = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e5", "expected_version": 2})
    assert illegal.status_code == 422
    stale = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 1})
    assert stale.status_code == 409

    r2 = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 2})
    assert r2.status_code == 200
    assert r2.json()["version"] == 3
    assert len(r2.json()["moves"]) == 2


def test_checkmate_ends_game(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    gid = _create(client)["id"]
    moves = [("f2f3", 1), ("e7e5", 2), ("g2g4", 3), ("d8h4", 4)]
    body: dict | None = None
    for uci, ver in moves:
        resp = client.post(f"/api/v1/games/{gid}/moves", json={"uci": uci, "expected_version": ver})
        assert resp.status_code == 200, resp.text
        body = resp.json()
    assert body is not None and body["status"] == "checkmate"
    over = client.post(
        f"/api/v1/games/{gid}/moves",
        json={"uci": "b1c3", "expected_version": body["version"]},
    )
    assert over.status_code == 409


def test_undo_flow(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    gid = _create(client)["id"]
    empty = client.post(f"/api/v1/games/{gid}/undo", json={"expected_version": 1})
    assert empty.status_code == 422
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    undone = client.post(f"/api/v1/games/{gid}/undo", json={"expected_version": 2})
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["fen"] == STARTING_FEN
    assert body["moves"] == []
    assert body["version"] == 3


def test_resign_flow(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    gid = _create(client)["id"]
    resp = client.post(f"/api/v1/games/{gid}/resign")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resigned"
    assert client.post(f"/api/v1/games/{gid}/resign").status_code == 409
    blocked = client.post(
        f"/api/v1/games/{gid}/moves",
        json={"uci": "e2e4", "expected_version": resp.json()["version"]},
    )
    assert blocked.status_code == 409


def test_draw_claim_rejected_early(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    gid = _create(client)["id"]
    assert client.post(f"/api/v1/games/{gid}/draw-claim").status_code == 422


def test_engine_move(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    local_gid = _create(client, mode="local")["id"]
    refused = client.post(f"/api/v1/games/{local_gid}/engine-move", json={"expected_version": 1})
    assert refused.status_code == 422

    gid = _create(client, mode="computer")["id"]
    # A computer game starts on the player's turn, so a bare engine-move is
    # refused: the loop replies automatically, this route only fills a gap.
    early = client.post(f"/api/v1/games/{gid}/engine-move", json={"expected_version": 1})
    assert early.status_code == 422

    # Submitting a human move now returns both plies in one response.
    moved = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["version"] == 3  # human ply + auto engine reply
    assert len(body["moves"]) == 2
    assert body["moves"][0]["uci"] == "e2e4"
