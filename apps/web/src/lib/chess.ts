/**
 * Client-side chess helpers. The backend is authoritative for legality and
 * outcomes; these helpers only render positions and preview UX hints.
 * FEN parsing here is display-only — moves are always validated server-side.
 */

export type Square = string; // e.g. 'e4'

export type Piece = {
  kind: 'p' | 'n' | 'b' | 'r' | 'q' | 'k';
  color: 'w' | 'b';
};

export type BoardMap = Map<Square, Piece>;

const FILES = 'abcdefgh';
const GLYPHS: Record<string, string> = {
  k: '♚',
  q: '♛',
  r: '♜',
  b: '♝',
  n: '♞',
  p: '♟',
};

/** Full Unicode glyph set for a piece (white uses outline glyphs). */
export function glyph(piece: Piece): string {
  const black = GLYPHS[piece.kind];
  if (piece.color === 'b') return black;
  // White outline variants.
  const white: Record<string, string> = {
    '♚': '♔',
    '♛': '♕',
    '♜': '♖',
    '♝': '♗',
    '♞': '♘',
    '♟': '♙',
  };
  return white[black];
}

/** Parse the piece-placement field of a FEN into a square→piece map. */
export function parseFenPlacement(fen: string): BoardMap {
  const board: BoardMap = new Map();
  const placement = fen.split(' ')[0];
  const ranks = placement.split('/');
  if (ranks.length !== 8) return board;
  ranks.forEach((row, rankIdx) => {
    const rank = 8 - rankIdx;
    let fileIdx = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        fileIdx += parseInt(ch, 10);
      } else {
        const square = `${FILES[fileIdx]}${rank}`;
        board.set(square, {
          kind: ch.toLowerCase() as Piece['kind'],
          color: ch === ch.toUpperCase() ? 'w' : 'b',
        });
        fileIdx += 1;
      }
    }
  });
  return board;
}

/** Side to move from a FEN string ('w' | 'b'). */
export function sideToMove(fen: string): 'w' | 'b' {
  return fen.split(' ')[1] === 'b' ? 'b' : 'w';
}

/** All 64 squares in display order (rank 8 → 1). */
export function allSquares(): Square[] {
  const squares: Square[] = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (let file = 0; file < 8; file += 1) {
      squares.push(`${FILES[file]}${rank}`);
    }
  }
  return squares;
}

/** Square color for the checkerboard pattern (a1 and h8 are dark). */
export function isLightSquare(square: Square): boolean {
  const file = FILES.indexOf(square[0]);
  const rank = parseInt(square[1], 10);
  return (file + rank) % 2 === 0;
}

/** Standard starting position piece placements, used to replay a move list. */
const STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

/**
 * Captured pieces per side, derived by replaying the authoritative UCI move list
 * (WEB-018). Unlike a material diff against the start, this stays correct under
 * promotion (a pawn becoming a queen is not a capture) and en-passant. A capture
 * is any move whose destination was occupied, plus the diagonal-into-empty
 * en-passant case. Display-only; the server owns game state.
 */
export function capturedPiecesFromMoves(moves: { uci: string }[]): {
  capturedByWhite: string[];
  capturedByBlack: string[];
} {
  const board = parseFenPlacement(STARTING_FEN);
  const capturedByWhite: string[] = [];
  const capturedByBlack: string[] = [];

  for (const { uci } of moves) {
    if (uci.length < 4) continue;
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    const promotion = uci.length >= 5 ? uci[4] : undefined;
    const mover = board.get(from);
    if (!mover) continue;

    // En-passant: a pawn's diagonal move into an empty square captures the pawn
    // that is left behind on the mover's original rank.
    const target = board.get(to);
    if (!target && mover.kind === 'p' && from[0] !== to[0]) {
      const captured: Piece = { kind: 'p', color: mover.color === 'w' ? 'b' : 'w' };
      (mover.color === 'w' ? capturedByWhite : capturedByBlack).push(glyph(captured));
    } else if (target) {
      (mover.color === 'w' ? capturedByWhite : capturedByBlack).push(glyph(target));
    }

    board.delete(from);
    board.set(to, promotion ? { kind: promotion as Piece['kind'], color: mover.color } : mover);

    // Castling: the rook hops with the king but captures nothing.
    if (mover.kind === 'k' && Math.abs(from.charCodeAt(0) - to.charCodeAt(0)) === 2) {
      const kingFile = to.charCodeAt(0);
      const rookFrom = kingFile > from.charCodeAt(0) ? 'h' : 'a';
      const rookTo = String.fromCharCode(kingFile + (kingFile > from.charCodeAt(0) ? -1 : 1));
      const rook = board.get(`${rookFrom}${mover.color === 'w' ? '1' : '8'}`);
      if (rook) {
        board.delete(`${rookFrom}${mover.color === 'w' ? '1' : '8'}`);
        board.set(`${rookTo}${mover.color === 'w' ? '1' : '8'}`, rook);
      }
    }
  }

  return { capturedByWhite, capturedByBlack };
}
