"""Chess-rules adapter over python-chess.

This module is the single place that imports the ``chess`` library, keeping the
domain model (:mod:`app.games.domain`) independent of the concrete rules engine.
"""

import chess

from app.games.domain import STARTING_FEN, Color, GameStatus, Move
from app.games.errors import IllegalMoveError, InvalidFenError, InvalidMoveError


class ChessRules:
    """Adapter for legal move generation, validation, and status detection."""

    def __init__(self, fen: str | None = None) -> None:
        position = fen if fen is not None else STARTING_FEN
        ChessRules.validate_fen(position)
        self._board = chess.Board(position)

    @classmethod
    def from_moves(cls, ucis: list[str], start_fen: str = STARTING_FEN) -> "ChessRules":
        """Rebuild a position by replaying ``ucis`` from ``start_fen``.

        A board constructed from a FEN alone carries no move history, so
        python-chess can never see a threefold repetition on it. Every persisted
        game keeps its full UCI history, which makes replay the correct way to
        evaluate status, repetition, and draw claims (CHS-014).

        Raises :class:`InvalidMoveError` / :class:`IllegalMoveError` if the
        stored history does not reproduce a legal game.
        """
        rules = cls(start_fen)
        rules.replay_moves(ucis)
        return rules

    @classmethod
    def initial_fen(cls) -> str:
        """Return the FEN of the standard starting position."""
        return STARTING_FEN

    @classmethod
    def validate_fen(cls, fen: str) -> None:
        """Raise :class:`InvalidFenError` if ``fen`` is not a valid position."""
        try:
            chess.Board(fen)
        except ValueError as exc:
            raise InvalidFenError(fen) from exc

    @classmethod
    def is_valid_fen(cls, fen: str) -> bool:
        """Return whether ``fen`` describes a valid chess position."""
        try:
            cls.validate_fen(fen)
        except InvalidFenError:
            return False
        return True

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn(self) -> Color:
        return Color.WHITE if self._board.turn == chess.WHITE else Color.BLACK

    @property
    def legal_move_ucis(self) -> list[str]:
        return [move.uci() for move in self._board.legal_moves]

    def is_legal(self, uci: str) -> bool:
        """Return whether ``uci`` is a legal move in the current position."""
        move = self._parse_uci(uci)
        return move in self._board.legal_moves

    def apply_move(self, uci: str) -> Move:
        """Apply a legal move, returning it as UCI + SAN.

        Raises :class:`InvalidMoveError` for unparsable UCI and
        :class:`IllegalMoveError` for moves that are not legal.
        """
        move = self._parse_uci(uci)
        if move not in self._board.legal_moves:
            raise IllegalMoveError(uci, self.fen)
        san = self._board.san(move)
        self._board.push(move)
        return Move(uci=move.uci(), san=san)

    def is_check(self) -> bool:
        return self._board.is_check()

    def fen_board(self) -> chess.Board:
        """A fresh, independent board for the current position.

        Search code pushes and pops moves on whatever board it is handed. This
        hands out a copy so engine exploration can never corrupt the history
        this object is keeping (that history is what makes threefold repetition
        detectable), while `rules.py` stays the only module importing `chess`.
        """
        return chess.Board(self.fen)

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    def is_insufficient_material(self) -> bool:
        return self._board.is_insufficient_material()

    def is_fifty_moves(self) -> bool:
        """Whether the fifty-move rule has actually advanced far enough."""
        return self._board.is_fifty_moves()

    def can_claim_draw(self) -> bool:
        """Whether the rules allow a draw claim right now (CHS-014)."""
        return self._board.can_claim_draw()

    def is_repetition(self, times: int = 3) -> bool:
        """Whether the current position has occurred ``times`` times.

        Only meaningful on a board built by replaying moves; a FEN-only board
        has no history to compare against.
        """
        return self._board.is_repetition(times)

    def status(self) -> GameStatus:
        """Derive the game status from the current position."""
        if self._board.is_checkmate():
            return GameStatus.CHECKMATE
        if self._board.is_stalemate():
            return GameStatus.STALEMATE
        if self._board.is_insufficient_material():
            return GameStatus.DRAW
        # Fifty-move rule and threefold repetition (CHS-014). Requires the
        # replayed move history — see ChessRules.from_moves.
        if self._board.can_claim_draw():
            return GameStatus.DRAW
        return GameStatus.ACTIVE

    def replay_moves(self, ucis: list[str]) -> list[Move]:
        """Apply a sequence of moves, returning the Move objects.

        Raises :class:`InvalidMoveError` or :class:`IllegalMoveError` if any move fails.
        """
        moves = []
        for uci in ucis:
            move = self.apply_move(uci)
            moves.append(move)
        return moves

    def undo_move(self) -> Move:
        """Undo the last move, returning the Move that was undone.

        Raises :class:`ValueError` if there are no moves to undo.
        """
        if not self._board.move_stack:
            raise ValueError("No moves to undo")
        move = self._board.pop()
        return Move(uci=move.uci(), san=self._board.san(move))

    def verify_invariants(self) -> list[str]:
        """Return a list of invariant violations (empty if all valid).

        Checks:
        - Exactly one king per side
        - Kings not on adjacent squares
        - Pawns not on first/last rank
        """
        violations = []

        # Count kings
        white_kings = len(self._board.pieces(chess.KING, chess.WHITE))
        black_kings = len(self._board.pieces(chess.KING, chess.BLACK))

        if white_kings != 1:
            violations.append(f"White has {white_kings} kings (expected 1)")
        if black_kings != 1:
            violations.append(f"Black has {black_kings} kings (expected 1)")

        # Check king adjacency if both present
        if white_kings == 1 and black_kings == 1:
            white_king_sq = self._board.king(chess.WHITE)
            black_king_sq = self._board.king(chess.BLACK)
            if (
                white_king_sq is not None
                and black_king_sq is not None
                and chess.square_distance(white_king_sq, black_king_sq) < 2
            ):
                violations.append("Kings are on adjacent or same square")

        # Check pawn ranks
        for square in self._board.pieces(chess.PAWN, chess.WHITE):
            rank = chess.square_rank(square)
            if rank == 7:  # White pawns on last rank
                violations.append(f"White pawn on last rank at {chess.square_name(square)}")

        for square in self._board.pieces(chess.PAWN, chess.BLACK):
            rank = chess.square_rank(square)
            if rank == 0:  # Black pawns on first rank
                violations.append(f"Black pawn on first rank at {chess.square_name(square)}")

        return violations

    def _parse_uci(self, uci: str) -> chess.Move:
        try:
            return chess.Move.from_uci(uci)
        except ValueError as exc:
            raise InvalidMoveError(uci) from exc
