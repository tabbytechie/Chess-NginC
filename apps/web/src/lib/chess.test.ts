import { describe, expect, it } from 'vitest';

import {
  allSquares,
  capturedPiecesFromMoves,
  glyph,
  isLightSquare,
  parseFenPlacement,
  sideToMove,
} from './chess';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

describe('parseFenPlacement', () => {
  it('places all 32 starting pieces', () => {
    expect(parseFenPlacement(START_FEN).size).toBe(32);
  });

  it('reads the piece on a square with color', () => {
    const board = parseFenPlacement(START_FEN);
    expect(board.get('e1')).toEqual({ kind: 'k', color: 'w' });
    expect(board.get('d8')).toEqual({ kind: 'q', color: 'b' });
    expect(board.get('e4')).toBeUndefined();
  });

  it('expands empty-square runs', () => {
    const board = parseFenPlacement('8/8/8/4k3/8/8/8/8 w - - 0 1');
    expect(board.size).toBe(1);
    expect(board.get('e5')).toEqual({ kind: 'k', color: 'b' });
  });

  it('returns an empty map for a malformed FEN rather than throwing', () => {
    expect(parseFenPlacement('nonsense').size).toBe(0);
  });
});

describe('sideToMove', () => {
  it('reads the active color', () => {
    expect(sideToMove(START_FEN)).toBe('w');
    expect(sideToMove('8/8/8/8/8/8/8/8 b - - 0 1')).toBe('b');
  });

  it('defaults to white when the field is missing', () => {
    expect(sideToMove('garbage')).toBe('w');
  });
});

describe('allSquares', () => {
  it('lists 64 squares in display order', () => {
    const squares = allSquares();
    expect(squares).toHaveLength(64);
    expect(squares[0]).toBe('a8');
    expect(squares[1]).toBe('b8');
    expect(squares[7]).toBe('h8');
    expect(squares[63]).toBe('h1');
  });

  it('has no duplicates', () => {
    expect(new Set(allSquares()).size).toBe(64);
  });
});

describe('isLightSquare', () => {
  it('treats a1 as dark and h1 as light', () => {
    expect(isLightSquare('a1')).toBe(false);
    expect(isLightSquare('h1')).toBe(true);
  });

  it('alternates along a rank', () => {
    // a8 is light; each step right flips the color.
    expect(isLightSquare('a8')).toBe(true);
    expect(isLightSquare('b8')).toBe(false);
    expect(isLightSquare('h8')).toBe(false);
  });
});

describe('glyph', () => {
  it('distinguishes white from black pieces', () => {
    expect(glyph({ kind: 'k', color: 'w' })).toBe('♔');
    expect(glyph({ kind: 'k', color: 'b' })).toBe('♚');
  });
});

describe('capturedPiecesFromMoves (WEB-018)', () => {
  it('reports nothing captured with no moves', () => {
    const { capturedByWhite, capturedByBlack } = capturedPiecesFromMoves([]);
    expect(capturedByWhite).toEqual([]);
    expect(capturedByBlack).toEqual([]);
  });

  it('credits White for a captured black pawn', () => {
    // 1. e4 d5 2. exd5
    const { capturedByWhite, capturedByBlack } = capturedPiecesFromMoves([
      { uci: 'e2e4' },
      { uci: 'd7d5' },
      { uci: 'e4d5' },
    ]);
    expect(capturedByWhite).toEqual(['♟']);
    expect(capturedByBlack).toEqual([]);
  });

  it('counts captures by both sides in order', () => {
    // 1. e4 d5 2. exd5 Qxd5 — White takes a pawn, Black's queen takes it back.
    const { capturedByWhite, capturedByBlack } = capturedPiecesFromMoves([
      { uci: 'e2e4' },
      { uci: 'd7d5' },
      { uci: 'e4d5' },
      { uci: 'd8d5' },
    ]);
    expect(capturedByWhite).toEqual(['♟']);
    expect(capturedByBlack).toEqual(['♙']);
  });

  it('detects an en-passant capture into an empty square', () => {
    // White pawn on e5 captures Black's double-stepping d-pawn en passant on d6.
    const { capturedByWhite } = capturedPiecesFromMoves([
      { uci: 'e2e4' },
      { uci: 'a7a6' },
      { uci: 'e4e5' },
      { uci: 'd7d5' },
      { uci: 'e5d6' },
    ]);
    expect(capturedByWhite).toEqual(['♟']);
  });

  it('does not count a castling rook move as a capture', () => {
    const { capturedByWhite, capturedByBlack } = capturedPiecesFromMoves([
      { uci: 'e2e4' },
      { uci: 'e7e5' },
      { uci: 'g1f3' },
      { uci: 'b8c6' },
      { uci: 'f1c4' },
      { uci: 'f8c5' },
      { uci: 'e1g1' },
    ]);
    expect(capturedByWhite).toEqual([]);
    expect(capturedByBlack).toEqual([]);
  });

  it('treats a promotion as a piece change, not phantom captured material', () => {
    // A pawn promotes on an empty square after its file clears; no capture added.
    const { capturedByWhite } = capturedPiecesFromMoves([
      { uci: 'b1a3' },
      { uci: 'a7a6' },
      { uci: 'a3b1' },
      { uci: 'a6a5' },
      { uci: 'b1a3' },
      { uci: 'a5a4' },
      { uci: 'a3b1' },
      { uci: 'a4a3' },
      { uci: 'b1a3' },
    ]);
    // The only capture is the black pawn taken on a3; a promotion adds none.
    expect(capturedByWhite).toEqual(['♟']);
  });
});
