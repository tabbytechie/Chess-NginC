/**
 * Chessboard (WEB-010/011/013/014/027): click-to-select + click-to-move,
 * promotion picker, keyboard operable, turn indicator. Display-only legality:
 * the server is authoritative (invalid moves surface as 422 errors).
 * Phase 6 accessibility: the board is a real ARIA `grid` (grid ▸ row ▸
 * gridcell), supports arrow-key navigation with a roving tab stop, Enter/Space
 * to select and target, an Escape-cancel/focus-trapped promotion dialog, and a
 * `busy` state that keeps the moving side's pieces live instead of blanking the
 * whole grid.
 */
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type RefObject,
} from 'react';

import { allSquares, glyph, isLightSquare, parseFenPlacement, sideToMove } from '../lib/chess';

type Props = {
  fen: string;
  status: string;
  selected: string | null;
  onSelect: (square: string | null) => void;
  onMove: (from: string, to: string, promotion?: string) => void;
  disabled?: boolean;
  lastMove?: { from: string; to: string } | null;
  inCheck?: boolean;
  flipped?: boolean;
};

const PROMOTION_PIECES = ['q', 'r', 'b', 'n'];
const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

function getPieceColor(color: string): 'white' | 'black' {
  return color === 'w' ? 'white' : 'black';
}

/** Move a square coordinate by a file/rank delta, returning null off-board. */
function adjacent(square: string, dFile: number, dRank: number): string | null {
  const file = FILES.indexOf(square[0]);
  const rank = Number(square[1]);
  const nf = file + dFile;
  const nr = rank + dRank;
  if (nf < 0 || nf > 7 || nr < 1 || nr > 8) return null;
  return `${FILES[nf]}${nr}`;
}

export default function Chessboard({
  fen,
  status,
  selected,
  onSelect,
  onMove,
  disabled = false,
  lastMove,
  inCheck = false,
  flipped = false,
}: Props) {
  const board = useMemo(() => parseFenPlacement(fen), [fen]);
  const squares = useMemo(() => (flipped ? [...allSquares()].reverse() : allSquares()), [flipped]);
  // Eight visual rows of eight cells give the grid its required `role="row"`
  // parents; `display: contents` keeps them transparent to the CSS layout.
  const rows = useMemo(() => {
    const out: string[][] = [];
    for (let r = 0; r < 8; r += 1) out.push(squares.slice(r * 8, r * 8 + 8));
    return out;
  }, [squares]);
  const turn = sideToMove(fen);
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(
    null,
  );
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const promoRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => () => setDragOver(null), []);

  // Roving tab stop: exactly one cell is tabbable, so `Tab` enters the grid once
  // and arrow keys move within it (the ARIA grid pattern).
  const tabStop = focused ?? squares[0];

  function moveFocus(current: string, dFile: number, dRank: number): void {
    const next = adjacent(current, dFile, dRank);
    if (!next) return;
    setFocused(next);
    boardRef.current?.querySelector<HTMLButtonElement>(`[data-square="${next}"]`)?.focus();
  }

  const turnLabel =
    status !== 'active' ? `Game over: ${status}` : `Turn: ${turn === 'w' ? 'White' : 'Black'}`;
  function isPromotionMove(from: string, to: string): boolean {
    const piece = board.get(from);
    if (!piece || piece.kind !== 'p') return false;
    const toRank = to[1];
    return (piece.color === 'w' && toRank === '8') || (piece.color === 'b' && toRank === '1');
  }
  function handleSquareClick(square: string) {
    if (disabled || status !== 'active') return;
    if (pendingPromotion) return;
    if (selected === null) {
      if (board.has(square)) onSelect(square);
      return;
    }
    if (selected === square) {
      onSelect(null);
      return;
    }
    if (isPromotionMove(selected, square)) {
      setPendingPromotion({ from: selected, to: square });
      return;
    }
    onMove(selected, square);
    onSelect(null);
  }
  function handleKey(event: KeyboardEvent<HTMLButtonElement>, square: string) {
    switch (event.key) {
      case 'ArrowUp':
        event.preventDefault();
        moveFocus(square, 0, flipped ? -1 : 1);
        break;
      case 'ArrowDown':
        event.preventDefault();
        moveFocus(square, 0, flipped ? 1 : -1);
        break;
      case 'ArrowLeft':
        event.preventDefault();
        moveFocus(square, flipped ? 1 : -1, 0);
        break;
      case 'ArrowRight':
        event.preventDefault();
        moveFocus(square, flipped ? -1 : 1, 0);
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        handleSquareClick(square);
        break;
      case 'Escape':
        onSelect(null);
        setPendingPromotion(null);
        break;
      default:
        break;
    }
  }
  function handleDragStart(square: string, event: DragEvent<HTMLButtonElement>) {
    if (disabled || status !== 'active') {
      event.preventDefault();
      return;
    }
    onSelect(square);
  }
  function handleDragOver(square: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (dragOver !== square) setDragOver(square);
  }
  function handleDrop(to: string, event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragOver(null);
    const from = selected;
    if (!from || from === to || disabled || status !== 'active') return;
    if (isPromotionMove(from, to)) {
      setPendingPromotion({ from, to });
      return;
    }
    onMove(from, to);
    onSelect(null);
  }

  // While `busy` (a move is in flight, typically the engine's reply), only the
  // side-to-move's pieces stay live; the rest of the grid is inert rather than
  // every square being disabled (which flickers the board and strips the tree).
  function cellDisabled(square: string): boolean {
    if (status !== 'active') return true;
    if (disabled) {
      const piece = board.get(square);
      return !(piece && piece.color === (turn === 'w' ? 'w' : 'b'));
    }
    return false;
  }

  const lastFrom = lastMove?.from;
  const lastTo = lastMove?.to;
  return (
    <section aria-label="chessboard" className="mb-xl">
      <p role="status" aria-live="polite" className="text-lg font-bold text-center mb-sm uppercase">
        {turnLabel}
      </p>
      <div
        className="board-wrapper"
        aria-label={`Chess position, ${turn === 'w' ? 'white' : 'black'} to move`}
      >
        <div className="board" role="grid" ref={boardRef}>
          {rows.map((row) => (
            <div key={row[0]} role="row" className="board-row">
              {row.map((square) => {
                const piece = board.get(square);
                const isSelected = selected === square;
                const isDraggable = !disabled && status === 'active' && Boolean(piece);
                return (
                  <button
                    key={square}
                    type="button"
                    role="gridcell"
                    data-square={square}
                    aria-label={`${square}${piece ? `, ${piece.color === 'w' ? 'white' : 'black'} ${piece.kind}` : ', empty'}${isSelected ? ', selected' : ''}`}
                    aria-pressed={isSelected}
                    draggable={isDraggable}
                    tabIndex={square === tabStop ? 0 : -1}
                    className={[
                      'square',
                      isLightSquare(square) ? 'light' : 'dark',
                      isSelected ? 'selected' : '',
                      lastFrom === square || lastTo === square ? 'last-move' : '',
                      inCheck && piece?.kind === 'k' ? 'in-check' : '',
                      dragOver === square ? 'dragover' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onClick={() => handleSquareClick(square)}
                    onFocus={() => setFocused(square)}
                    onKeyDown={(e) => handleKey(e, square)}
                    onDragStart={(e) => handleDragStart(square, e)}
                    onDragOver={(e) => handleDragOver(square, e)}
                    onDragLeave={() => setDragOver((cur) => (cur === square ? null : cur))}
                    onDrop={(e) => handleDrop(square, e)}
                    disabled={cellDisabled(square)}
                  >
                    {piece && (
                      <span className={`piece ${getPieceColor(piece.color)}`} aria-hidden="true">
                        {glyph(piece)}
                      </span>
                    )}
                    <span className="coord" aria-hidden="true">
                      {square}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      {pendingPromotion && (
        <PromotionPicker
          from={pendingPromotion.from}
          to={pendingPromotion.to}
          pickerRef={promoRef}
          onPick={(kind) => {
            onMove(pendingPromotion.from, pendingPromotion.to, kind);
            setPendingPromotion(null);
            onSelect(null);
          }}
          onCancel={() => {
            setPendingPromotion(null);
            onSelect(null);
          }}
        />
      )}
    </section>
  );
}

type PromotionPickerProps = {
  from: string;
  to: string;
  pickerRef: RefObject<HTMLDivElement | null>;
  onPick: (kind: string) => void;
  onCancel: () => void;
};

/**
 * Modal promotion chooser: initial focus on the first option, a Tab focus trap,
 * and Escape to cancel — so keyboard and screen-reader users can complete it.
 */
function PromotionPicker({ from, to, pickerRef, onPick, onCancel }: PromotionPickerProps) {
  useEffect(() => {
    pickerRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
  }, [pickerRef]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== 'Tab' || !pickerRef.current) return;
    const buttons = Array.from(pickerRef.current.querySelectorAll<HTMLButtonElement>('button'));
    if (buttons.length === 0) return;
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="choose promotion piece"
      className="promotion-picker"
      ref={pickerRef}
      onKeyDown={handleKeyDown}
    >
      <p>
        Promote pawn {from} → {to} to:
      </p>
      <div className="promotion-grid">
        {PROMOTION_PIECES.map((kind) => (
          <button
            key={kind}
            type="button"
            aria-label={`promote to ${kind}`}
            onClick={() => onPick(kind)}
          >
            {kind.toUpperCase()}
          </button>
        ))}
      </div>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}
