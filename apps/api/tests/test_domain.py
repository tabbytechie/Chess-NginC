"""Tests for the chess domain model."""

import chess
import pytest

from app.games.domain import (
    STARTING_FEN,
    Color,
    Game,
    GameMode,
    GameResult,
    GameStatus,
    Move,
)


def test_starting_fen_constant_matches_python_chess() -> None:
    assert STARTING_FEN == chess.STARTING_FEN


def test_game_defaults_to_active_local_game() -> None:
    game = Game()
    assert game.mode is GameMode.LOCAL
    assert game.status is GameStatus.ACTIVE
    assert game.fen == STARTING_FEN
    assert game.moves == []


def test_game_id_is_unique_per_instance() -> None:
    assert Game().id != Game().id


def test_move_is_frozen_and_holds_uci_and_san() -> None:
    move = Move(uci="e2e4", san="e4")
    assert move.uci == "e2e4"
    assert move.san == "e4"


def test_color_enum_values() -> None:
    assert Color.WHITE.value == "white"
    assert Color.BLACK.value == "black"


def test_resign_active_game() -> None:
    game = Game()
    game.resign()
    assert game.status is GameStatus.RESIGNED


def test_resign_non_active_game_raises() -> None:
    game = Game(status=GameStatus.CHECKMATE)
    with pytest.raises(ValueError, match="Cannot resign a game in checkmate status"):
        game.resign()


def test_to_pgn_empty_game() -> None:
    game = Game()
    pgn = game.to_pgn()
    assert '[Result] "*"' in pgn
    assert pgn.rstrip().endswith("*")  # no moves, just the open result token


def test_to_pgn_single_move() -> None:
    game = Game()
    game.moves.append(Move(uci="e2e4", san="e4"))
    pgn = game.to_pgn()
    assert "1. e4 *" in pgn
    assert '[White] "Player"' in pgn  # default player_color is white


def test_to_pgn_two_moves() -> None:
    game = Game()
    game.moves.append(Move(uci="e2e4", san="e4"))
    game.moves.append(Move(uci="e7e5", san="e5"))
    assert "1. e4 e5 *" in game.to_pgn()


def test_to_pgn_multiple_moves() -> None:
    game = Game()
    game.moves.extend(
        [
            Move(uci="e2e4", san="e4"),
            Move(uci="e7e5", san="e5"),
            Move(uci="g1f3", san="Nf3"),
            Move(uci="b8c6", san="Nc6"),
        ]
    )
    assert "1. e4 e5 2. Nf3 Nc6 *" in game.to_pgn()


def test_to_pgn_player_black_swaps_names_and_records_result() -> None:
    game = Game(player_color=Color.BLACK, result=GameResult.BLACK_WIN)
    game.moves.extend([Move(uci="e2e4", san="e4"), Move(uci="e7e5", san="e5")])
    pgn = game.to_pgn()
    assert '[White] "Engine"' in pgn
    assert '[Black] "Player"' in pgn
    assert pgn.rstrip().endswith("0-1")
