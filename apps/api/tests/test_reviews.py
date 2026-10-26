"""Game review tests: classifier grades, coaching text, analysis pipeline,
and the POST/GET review endpoints (REVIEW-001..005)."""

import chess
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.serializers import to_review_response
from app.engine.classifier import (
    MoveContext,
    MoveQuality,
    centipawn_loss,
    classify_move,
)
from app.engine.provider import (
    AnalyseRequest,
    AnalysisResult,
    BatchedEngineProvider,
    PrincipalVariation,
)
from app.engine.stockfish import StockfishUnavailableError
from app.models.game_move import GameMove as GameMoveRow
from app.models.game_review import GameReview
from app.reviews import service as review_service
from app.reviews.annotate import annotate_moves
from app.reviews.explainer import explain_move
from app.reviews.service import _accuracy, analyse_game

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _grade(loss: int, is_best: bool = False, **ctx: object) -> MoveQuality:
    return classify_move(loss, is_best, MoveContext(**ctx))  # type: ignore[arg-type]


class TestClassifier:
    def test_bands(self) -> None:
        assert _grade(5) is MoveQuality.EXCELLENT
        assert _grade(20) is MoveQuality.GOOD
        assert _grade(100) is MoveQuality.INACCURACY
        assert _grade(300) is MoveQuality.MISTAKE
        assert _grade(600) is MoveQuality.BLUNDER

    def test_best_and_brilliant(self) -> None:
        assert _grade(0, True) is MoveQuality.BEST
        # Engine-top capture of a minor+ piece = the sparkly sacrifice grade.
        assert _grade(0, True, captures_value_cp=300) is MoveQuality.BRILLIANT
        # ...but not when it was the only legal move.
        assert _grade(0, True, captures_value_cp=300, is_forced=True) is MoveQuality.BEST

    def test_forced_moves_cannot_be_blunders(self) -> None:
        assert _grade(999, False, is_forced=True) is MoveQuality.GOOD

    def test_centipawn_loss_with_mates(self) -> None:
        # Letting a forced mate escape is a colossal loss.
        assert centipawn_loss(0, 5, best_mate=1, played_mate=None) > 99_000
        # Faster mate beats slower mate.
        assert centipawn_loss(0, 0, best_mate=1, played_mate=3) == 2000
        assert centipawn_loss(0, 0) == 0

    def test_quality_values_are_stable_strings(self) -> None:
        assert {q.value for q in MoveQuality} == {
            "brilliant",
            "best",
            "excellent",
            "good",
            "inaccuracy",
            "mistake",
            "blunder",
        }


class TestExplainer:
    def _explain(self, fen: str, uci: str, quality: str, **kw: object) -> str:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, f"{uci} is not legal in {fen}"
        return explain_move(
            fen,
            move,
            quality,
            kw.get("loss_cp", 0),  # type: ignore[arg-type]
            kw.get("eval_after_cp", 0),  # type: ignore[arg-type]
            kw.get("best_uci", ""),  # type: ignore[arg-type]
            kw.get("is_best", False),  # type: ignore[arg-type]
        )

    def test_blunder_names_the_alternative(self) -> None:
        text = self._explain(START_FEN, "e2e4", "blunder", loss_cp=600, best_uci="d2d4")
        assert "blunder" in text
        assert "d4" in text  # the alternative rendered as SAN

    def test_capture_mentions_the_victim(self) -> None:
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        text = self._explain(fen, "e4d5", "best", is_best=True)
        assert "taking black’s pawn" in text

    def test_best_move_praise_line(self) -> None:
        text = self._explain(START_FEN, "e2e4", "best", is_best=True)
        assert "engine wants" in text


class _ScriptedProvider:
    """Fake analysis provider: ranks legal moves deterministically.

    First legal move (sorted UCI) is 'best' at 20 cp; later ones lose 10 cp
    each, so a scripted game yields a stable mix of grades.
    """

    name = "scripted"

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        board = chess.Board(request.fen)
        legal = sorted(m.uci() for m in board.legal_moves)
        lines = tuple(
            PrincipalVariation(move=m, score_cp=20 - 10 * i, pv=(m,))
            for i, m in enumerate(legal[:3])
        )
        return AnalysisResult(fen=request.fen, lines=lines, provider=self.name)


def _rows(ucis: list[str]) -> list[GameMoveRow]:
    """Build GameMove rows for a legal replay (unpersisted; ids irrelevant)."""
    board = chess.Board(START_FEN)
    rows = []
    for uci in ucis:
        move = chess.Move.from_uci(uci)
        rows.append(GameMoveRow(uci=uci, san=board.san(move), move_number=len(rows) + 1))
        board.push(move)
    return rows


_PIECE_CP = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}


class _MaterialProvider:
    """A stand-in engine whose numbers mean something: the material on the board,
    plus whatever the side to move can take for free.

    `analyse_game` reads the value of a position from its own analysis, so a
    graded loss becomes a fact the test can check against the chess itself —
    which is exactly what the -800 placeholder could not do (TD-017).
    """

    name = "material"

    def __init__(self) -> None:
        self.fens: list[str] = []

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        self.fens.append(request.fen)
        board = chess.Board(request.fen)
        balance = sum(
            _PIECE_CP[piece.symbol().lower()] * (1 if piece.color == chess.WHITE else -1)
            for piece in board.piece_map().values()
        )
        cp = balance if board.turn == chess.WHITE else -balance
        cp += self._free_material(board, board.turn)
        legal = sorted(m.uci() for m in board.legal_moves)
        lines = tuple(PrincipalVariation(move=m, score_cp=cp, pv=(m,)) for m in legal[:3])
        return AnalysisResult(fen=request.fen, lines=lines, provider=self.name)

    @staticmethod
    def _free_material(board: chess.Board, side: chess.Color) -> int:
        """Material `side` can capture right now with nothing recapturing.

        Deliberately crude — pins and king safety are ignored. It only has to
        make a hung queen worth 900 in these fixtures.
        """
        enemy = not side
        gain = 0
        for square, piece in board.piece_map().items():
            if piece.color != enemy or piece.piece_type == chess.KING:
                continue
            if board.is_attacked_by(side, square) and not board.is_attacked_by(enemy, square):
                gain += _PIECE_CP[piece.symbol().lower()]
        return gain


class TestAccuracy:
    """The report-card figure: 100 for errorless play, decaying with loss.

    Anchors are deliberate, not incidental — a perfect game must never read 0%.
    """

    def test_anchors(self) -> None:
        assert _accuracy([]) == 100
        assert _accuracy([0, 0, 0]) == 100
        assert _accuracy([10]) == 96
        assert _accuracy([100]) == 67
        assert _accuracy([250]) == 37
        assert _accuracy([5000]) == 0

    def test_monotone_decreasing(self) -> None:
        assert _accuracy([0]) > _accuracy([50]) > _accuracy([200]) > _accuracy([400])

    def test_worst_case_clamped(self) -> None:
        # A missed mate costs tens of thousands of centipawns: still 0, never negative.
        assert _accuracy([40000]) == 0


class TestAnalyseGame:
    def test_pipeline_classifies_every_ply(self) -> None:
        payload = analyse_game(_ScriptedProvider(), _rows(["e2e4", "e7e5", "g1f3", "b8c6"]))
        moves = payload["moves"]
        assert [m["ply"] for m in moves] == [1, 2, 3, 4]
        assert [m["color"] for m in moves] == ["w", "b", "w", "b"]
        assert moves[0]["pre_fen"] == START_FEN
        assert moves[1]["pre_fen"] != START_FEN  # each ply carries its own position
        assert all(m["quality"] in {q.value for q in MoveQuality} for m in moves)
        assert all(m["explanation"] for m in moves)
        # Graph is white-perspective and same length as plies.
        assert len(payload["eval_graph"]) == 4
        counts = payload["counts"]
        assert sum(counts.values()) == 4
        assert 0 <= payload["summary"]["accuracy"]["w"] <= 100

    def test_flawless_scripted_game_scores_full_accuracy(self) -> None:
        """Play the provider's own top line every ply: the report card must read
        100, not 0 — the bug the first accuracy formula shipped with."""
        board = chess.Board(START_FEN)
        ucis: list[str] = []
        for _ in range(4):
            top = sorted(m.uci() for m in board.legal_moves)[0]
            ucis.append(top)
            board.push(chess.Move.from_uci(top))
        payload = analyse_game(_ScriptedProvider(), _rows(ucis))
        assert all(m["centipawn_loss"] == 0 for m in payload["moves"])
        assert payload["summary"]["accuracy"] == {"w": 100, "b": 100}

    def test_off_window_move_is_graded_by_the_position_it_left(self) -> None:
        """TD-017: a move the MultiPV window never ranked used to be given a flat
        -800, so every off-window move was a blunder by construction. It now
        takes its value from the position the move actually produced."""
        provider = _ScriptedProvider()
        lines = provider.analyse(AnalyseRequest(fen=START_FEN)).lines
        assert "h7h6" not in [line.move for line in lines]
        payload = analyse_game(provider, _rows(["e2e4", "h7h6"]))
        played = payload["moves"][1]
        # The scripted window is worth 20 cp to the mover; the following position
        # is worth 20 cp to the opponent, so the honest loss is 40 — a small one.
        assert played["centipawn_loss"] == 40
        assert played["quality"] == "good"
        assert played["eval_cp"] == -20

    def test_hanging_a_queen_costs_a_queen(self) -> None:
        provider = _MaterialProvider()
        payload = analyse_game(provider, _rows(["e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d5g2"]))
        # ...Qxg2 walks into Bxg2: nothing in the top-3 window says so, the
        # position after the move does.
        blunder = payload["moves"][5]
        assert blunder["quality"] == "blunder"
        assert 400 <= blunder["centipawn_loss"] < 1000
        # And it reaches the "where you could have done better" list.
        assert [i["ply"] for i in payload["improvements"]] == [6]

    def test_hanging_a_pawn_costs_a_pawn(self) -> None:
        """The same mechanism, one size down: this used to read as a blunder too."""
        payload = analyse_game(_MaterialProvider(), _rows(["e2e4", "e7e5", "b2b4"]))
        pawn_push = payload["moves"][2]
        assert pawn_push["centipawn_loss"] == 100
        assert pawn_push["quality"] == "inaccuracy"

    def test_finished_position_is_scored_by_the_rules_not_the_engine(self) -> None:
        """An engine asked about a mated position answers with nothing, so the
        final ply is valued from the board itself — and never searched."""
        provider = _MaterialProvider()
        payload = analyse_game(provider, _rows(["f2f3", "e7e5", "g2g4", "d8h4"]))
        final = payload["moves"][3]
        assert final["eval_mate"] == 1
        assert final["centipawn_loss"] == 0
        assert final["quality"] in {"best", "excellent", "brilliant"}

        board = chess.Board()
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            board.push(chess.Move.from_uci(uci))
        assert board.is_checkmate()
        # One search per ply, no extra search for the dead position.
        assert len(provider.fens) == 4
        assert board.fen() not in provider.fens

    def test_unplayed_fallback_precedence(self) -> None:
        """The pessimistic placeholder survives only where nothing else is known."""
        from app.reviews.service import _line_score

        window = (PrincipalVariation(move="e2e4", score_cp=20),)
        # A real position value wins over the placeholder.
        assert _line_score(window, "a1a2", (-150, None)) == (-150, None, False)
        # With no following analysis at all, fall back to the pessimistic guess.
        assert _line_score(window, "a1a2", None) == (-780, None, False)
        # And an engine that said nothing about this position yields no grades.
        assert _line_score((), "a1a2", None) == (0, None, False)

    def test_capture_value_reads_a_white_victim(self) -> None:
        """Black taking a White pawn used to be worth 0 cp: `Piece.symbol()` is
        color-cased, and the value table is keyed by the lowercase letters."""
        from app.reviews.service import _captures_value

        board = chess.Board(START_FEN)
        for uci in ("e2e4", "e7e5", "b2b4"):
            board.push(chess.Move.from_uci(uci))
        capture = chess.Move.from_uci("f8b4")
        assert capture in board.legal_moves
        assert _captures_value(board, capture) == 100
        assert _captures_value(board, chess.Move.from_uci("g8f6")) == 0

    def test_unparsable_stored_move_rejected(self) -> None:
        from app.reviews.service import ReviewTargetError

        with pytest.raises(ReviewTargetError):
            analyse_game(_ScriptedProvider(), [GameMoveRow(uci="nope", san="?", move_number=1)])

    def test_illegal_move_is_rejected_before_any_search(self) -> None:
        from app.reviews.service import ReviewTargetError

        provider = _MaterialProvider()
        rows = _rows(["e2e4"]) + [GameMoveRow(uci="a1a8", san="?", move_number=2)]
        with pytest.raises(ReviewTargetError):
            analyse_game(provider, rows)
        assert provider.fens == []  # validation costs no engine time


def _finished_local_game(client: TestClient) -> int:
    gid = client.post("/api/v1/games", json={"mode": "local"}).json()["id"]
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 2})
    assert client.post(f"/api/v1/games/{gid}/resign").status_code == 200
    return gid


class TestReviewEndpoints:
    def test_post_generates_and_get_serves_cached(
        self,
        authed_client: tuple[TestClient, dict],
        fake_binary: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assert fake_binary  # PATH-resolved fake UCI engine stands in for Stockfish
        monkeypatch.setattr("app.reviews.service.REVIEW_TIME_MS", 100)
        client, _ = authed_client
        gid = _finished_local_game(client)

        resp = client.post(f"/api/v1/games/{gid}/review", json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["game_id"] == gid
        assert len(body["moves"]) == 2
        assert body["summary"]["ply_count"] == 2

        cached = client.get(f"/api/v1/games/{gid}/review")
        assert cached.status_code == 200
        assert cached.json()["id"] == body["id"]  # served without re-analysis

        forced = client.post(f"/api/v1/games/{gid}/review", json={"force": True})
        assert forced.status_code == 200
        assert forced.json()["id"] == body["id"]  # row updated in place

    def test_active_game_is_422(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        gid = client.post("/api/v1/games", json={"mode": "local"}).json()["id"]
        assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 422

    def test_finished_without_moves_is_422(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        gid = client.post("/api/v1/games", json={"mode": "local"}).json()["id"]
        client.post(f"/api/v1/games/{gid}/resign")
        assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 422

    def test_get_without_review_is_409(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        gid = _finished_local_game(client)
        assert client.get(f"/api/v1/games/{gid}/review").status_code == 409

    def test_foreign_game_is_404(
        self, authed_client: tuple[TestClient, dict], other_client: TestClient
    ) -> None:
        client, _ = authed_client
        gid = _finished_local_game(client)
        assert other_client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 404
        assert other_client.get(f"/api/v1/games/{gid}/review").status_code == 404

    def test_missing_binary_stores_failed_review(
        self,
        authed_client: tuple[TestClient, dict],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Engine down is a stored, displayable outcome — not a 500.
        def boom(*_a: object, **_k: object) -> object:
            raise StockfishUnavailableError("no binary in tests")

        monkeypatch.setattr("app.reviews.service.open_stockfish_provider", boom)
        client, _ = authed_client
        gid = _finished_local_game(client)
        resp = client.post(f"/api/v1/games/{gid}/review", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert "no binary" in (resp.json()["error"] or "")


class _KernelStubProvider:
    """Wraps a plain analysis provider with the batch protocol (kernel tests)."""

    name = "kernel-scripted"

    def __init__(self, inner: _ScriptedProvider) -> None:
        self._inner = inner

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        return self._inner.analyse(request)

    def __enter__(self) -> BatchedEngineProvider:
        return self  # type: ignore[return-value]

    def __exit__(self, *args: object) -> None:
        return None


class TestGenerateOrGetKernel:
    """RB-002: the kernel is replay → commit (release) → search → short write."""

    def test_kernel_stores_exactly_what_direct_analysis_produces(
        self, authed_client: tuple[TestClient, dict], db: Session
    ) -> None:
        client, user = authed_client
        gid = _finished_local_game(client)
        repo_moves = review_service._game_moves(db, gid)

        # One and the same scripted provider answers both paths, so identical
        # output can only fail on a wiring bug — never on engine nondeterminism.
        scripted = _ScriptedProvider()
        direct = analyse_game(scripted, repo_moves)

        def factory(*_a: object, **_k: object) -> _KernelStubProvider:
            return _KernelStubProvider(scripted)

        monkey = pytest.MonkeyPatch()
        try:
            monkey.setattr(review_service, "open_stockfish_provider", factory)
            review = review_service.generate_or_get(db, gid, user["id"])
        finally:
            monkey.undo()

        assert review.status == "completed"
        assert review.payload == direct
        assert review.provider == _KernelStubProvider.name
        assert review.depth == review_service.REVIEW_DEPTH
        assert review.hero_color == "w"
        # The kernel committed its row for real — the same session reads it back.
        assert db.query(GameReview).filter_by(game_id=gid).one().payload == direct

    def test_connection_is_released_across_the_engine_batch(
        self, authed_client: tuple[TestClient, dict], db: Session
    ) -> None:
        # The session is bound to the test engine, so that engine's pool is the
        # observation point: when the seconds-long batch runs, the session must
        # hold nothing — no open transaction and no checked-out connection.
        client, user = authed_client
        gid = _finished_local_game(client)
        seen: list[bool] = []

        original = review_service.analyse_plies

        def spy(provider: object, plies: object, final_board: object) -> dict:
            held = db.in_transaction() or db.get_bind().pool.checkedout() > 0
            seen.append(held)
            return original(provider, plies, final_board)  # type: ignore[arg-type]

        def stub_factory(*_a: object, **_k: object) -> _KernelStubProvider:
            return _KernelStubProvider(_ScriptedProvider())

        monkey = pytest.MonkeyPatch()
        try:
            monkey.setattr(review_service, "analyse_plies", spy)
            monkey.setattr(review_service, "open_stockfish_provider", stub_factory)
            review = review_service.generate_or_get(db, gid, user["id"])
        finally:
            monkey.undo()

        assert seen == [False]  # searched with no transaction and no held connection
        assert review.status == "completed"


class TestReviewHttpCache:
    """RB-005: the GET path carries a stable content ETag + 304 revalidation."""

    @pytest.fixture(autouse=True)
    def _deterministic_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Patch the whole scenario onto one deterministic engine (forced re-run
        # included), so a byte-identical payload is a fact about the code, not a
        # coin-flip on a real engine — the validator must never churn for it.
        def factory(*_a: object, **_k: object) -> _KernelStubProvider:
            return _KernelStubProvider(_ScriptedProvider())

        monkeypatch.setattr(review_service, "open_stockfish_provider", factory)

    def _first_etag(self, client: TestClient) -> tuple[int, str]:
        gid = _finished_local_game(client)
        assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 200
        first = client.get(f"/api/v1/games/{gid}/review")
        assert first.status_code == 200
        assert first.headers["ETag"]
        assert first.headers["cache-control"] == "private, no-cache"
        assert "etag" not in first.headers["vary"].lower()
        return gid, first.headers["ETag"]

    def test_etag_is_stable_and_304_skips_the_body(
        self, authed_client: tuple[TestClient, dict]
    ) -> None:
        client, _ = authed_client
        gid, etag = self._first_etag(client)

        again = client.get(f"/api/v1/games/{gid}/review", headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["ETag"] == etag

        forced = client.post(f"/api/v1/games/{gid}/review", json={"force": True})
        assert forced.status_code == 200
        after = client.get(f"/api/v1/games/{gid}/review", headers={"If-None-Match": etag})
        # Byte-identical re-analysis: the row was rewritten, the content was not,
        # so the recomputed validator still matches — and a plain GET without the
        # header keeps serving the body.
        assert after.status_code == 304
        plain = client.get(f"/api/v1/games/{gid}/review")
        assert plain.status_code == 200
        assert plain.headers["ETag"] == etag

    def test_other_players_never_share_the_validator(
        self, authed_client: tuple[TestClient, dict], other_client: TestClient
    ) -> None:
        client, _ = authed_client
        gid, etag = self._first_etag(client)
        stale = client.get(f"/api/v1/games/{gid}/review", headers={"If-None-Match": '"deadbeef"'})
        assert stale.status_code == 200
        assert stale.headers["ETag"] == etag
        # A foreign reviewer gets the ownership answer (404), never a 304.
        foreign = other_client.get(f"/api/v1/games/{gid}/review", headers={"If-None-Match": etag})
        assert foreign.status_code == 404


def _payload_plies(sans: list[str], cp: int = 100, mate: int | None = None) -> list[dict]:
    """Replay SAN into the shape `analyse_game` stores.

    `eval_cp` is written from the mover's point of view, exactly as the review
    service does it, so the annotation's perspective flip is a real test.
    """
    board = chess.Board(START_FEN)
    entries: list[dict] = []
    for index, san in enumerate(sans):
        pre_fen = board.fen()
        mover_is_white = board.turn
        move = board.push_san(san)
        entries.append(
            {
                "ply": index + 1,
                "move_number": index // 2 + 1,
                "uci": move.uci(),
                "san": san,
                "pre_fen": pre_fen,
                "color": "w" if mover_is_white else "b",
                "quality": "best",
                "centipawn_loss": 0,
                "best_uci": move.uci(),
                "eval_cp": cp,
                "eval_mate": mate,
                "explanation": "test line",
            }
        )
    return entries


class TestReviewAnnotation:
    """Derived fields computed on the way out (REVIEW-008 / ANL-004 / COA-004)."""

    RUY_LOPEZ = ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "h6"]

    def test_every_ply_gets_the_four_fields(self) -> None:
        annotated = annotate_moves(_payload_plies(self.RUY_LOPEZ))
        for item in annotated:
            assert {"opening_eco", "opening_name", "in_book", "win_pct"} <= set(item)
        assert annotated[4]["opening_eco"] == "C60"
        assert annotated[4]["opening_name"] == "Ruy Lopez"
        assert annotated[4]["in_book"] is True

    def test_the_name_survives_leaving_the_book(self) -> None:
        # Theory names a position, not a mistake: once play has gone off the book
        # the panel still says which opening got there, flagged as out of book.
        annotated = annotate_moves(_payload_plies(self.RUY_LOPEZ))
        off_book = annotated[-1]
        assert off_book["in_book"] is False
        assert off_book["opening_name"] == "Ruy Lopez: Morphy Defense"
        assert off_book["opening_eco"] == "C70"

    def test_first_ply_of_an_unlisted_line_has_no_name(self) -> None:
        # A stored ply whose position chess cannot read is a gap, not a crash.
        moves = [{"pre_fen": "not a fen", "uci": "e2e4", "color": "w", "eval_cp": 0}]
        annotated = annotate_moves(moves)
        assert annotated[0]["opening_name"] is None
        assert annotated[0]["in_book"] is False

    def test_expectancy_is_reported_from_white_side(self) -> None:
        # Both plies were stored as +100 cp for the player who moved, so one of
        # them is a one-pawn edge and the other is not.
        annotated = annotate_moves(_payload_plies(["e4", "e5"]))
        assert annotated[0]["win_pct"] == 76
        assert annotated[1]["win_pct"] == 24

    def test_mate_is_flipped_the_same_way(self) -> None:
        annotated = annotate_moves(_payload_plies(["e4", "e5"], cp=0, mate=4))
        assert annotated[0]["win_pct"] == 99
        assert annotated[1]["win_pct"] == 1

    def test_a_ply_without_an_evaluation_stays_unknown(self) -> None:
        moves = [{"pre_fen": START_FEN, "uci": "e2e4", "color": "w"}]
        assert annotate_moves(moves)[0]["win_pct"] is None

    def test_the_stored_payload_is_never_touched(self) -> None:
        # Annotation is a read-side view: the JSON in the database is not rewritten.
        moves = _payload_plies(["e4", "e5"])
        before = [dict(item) for item in moves]
        annotated = annotate_moves(moves)
        assert moves == before
        assert all(item["opening_name"] is not None for item in annotated)
        assert all(id(item) not in {id(m) for m in moves} for item in annotated)

    def test_a_row_saved_before_these_fields_still_serialises(self) -> None:
        row = GameReview(
            id=1,
            game_id=7,
            status="completed",
            provider="stockfish",
            depth=15,
            hero_color="w",
            payload={
                "summary": {"ply_count": 2, "accuracy": {"w": 90, "b": 82}},
                "counts": {"best": 2},
                "moves": _payload_plies(["e4", "e5"]),
                "eval_graph": [],
                "improvements": [],
            },
        )
        response = to_review_response(row)
        first = response.moves[0]
        assert first.opening_eco == "B00"
        assert first.in_book is True
        assert first.win_pct == 76
        # And it goes out to the wire as plain JSON.
        assert response.model_dump(mode="json")["moves"][0]["opening_name"] == "King's Pawn Game"
