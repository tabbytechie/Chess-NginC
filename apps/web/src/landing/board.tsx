/**
 * The floating holographic board in the "Play" scene: a perspective-tilted
 * chessboard that drifts over a glowing pool while a curated opening line
 * (Evans Gambit Accepted) plays itself out — pieces glide square to square,
 * a streak of light traces every move, hit squares pulse and a sheen sweeps
 * the board. The board is veiled and edge-masked so the scene's light grades
 * it like the painted art, blending it into the descent. Also exports the
 * ambient shooting-light Streaks used by the hero and finale skies. Colours
 * come from the landing theme tokens, so the board re-skins night/day.
 */
import { useEffect, useRef, useState } from 'react';

import PieceIcon from '../components/PieceIcon';
import { mm } from './effects';

interface PieceT {
  id: string;
  kind: string;
  color: 'w' | 'b';
  f: number; // file 0..7 (a..h)
  r: number; // rank 0..7 (rank 1..8)
  moving?: boolean;
  captured?: boolean;
}

interface Trail {
  key: number;
  x: number; // % of board
  y: number;
  len: number; // %
  ang: number; // deg
}

const sq = (s: string) => ({ f: s.charCodeAt(0) - 97, r: Number(s[1]) - 1 });

const BACK = ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'];

function initialPieces(): PieceT[] {
  const out: PieceT[] = [];
  for (const color of ['w', 'b'] as const) {
    const row = color === 'w' ? 0 : 7;
    BACK.forEach((kind, f) => out.push({ id: `${color}-${kind}-${f}`, kind, color, f, r: row }));
    for (let f = 0; f < 8; f++) out.push({ id: `${color}-p-${f}`, kind: 'p', color, f, r: color === 'w' ? 1 : 6 });
  }
  return out;
}

/** one ply = one or more {from,to} hops (castling is two); captures are automatic */
const LINE: { from: string; to: string }[][] = [
  [{ from: 'e2', to: 'e4' }],
  [{ from: 'e7', to: 'e5' }],
  [{ from: 'g1', to: 'f3' }],
  [{ from: 'b8', to: 'c6' }],
  [{ from: 'f1', to: 'c4' }],
  [{ from: 'f8', to: 'c5' }],
  [{ from: 'b2', to: 'b4' }],
  [{ from: 'c5', to: 'b4' }], // Bxb4
  [{ from: 'c2', to: 'c3' }],
  [{ from: 'b4', to: 'a5' }],
  [{ from: 'd2', to: 'd4' }],
  [{ from: 'e5', to: 'd4' }], // exd4
  [
    { from: 'e1', to: 'g1' }, // O-O
    { from: 'h1', to: 'f1' },
  ],
  [{ from: 'd4', to: 'd3' }],
  [{ from: 'f1', to: 'e1' }], // Re1
  [{ from: 'g8', to: 'e7' }], // Nge7
  [{ from: 'c1', to: 'g5' }], // Bg5
];

const cx = (f: number) => (f + 0.5) * 12.5;
const cy = (r: number) => (7 - r + 0.5) * 12.5;

export function BoardFeature() {
  const [pieces, setPieces] = useState<PieceT[]>(initialPieces);
  const [trails, setTrails] = useState<Trail[]>([]);
  const piecesRef = useRef<PieceT[]>(initialPieces());
  const stepRef = useRef(0);
  const trailKey = useRef(0);

  useEffect(() => {
    // reduced motion: the board shows the starting position, still.
    if (mm('(prefers-reduced-motion: reduce)')) return;
    let timer = 0;
    // captures schedule a short prune after the fade-out; track them so an
    // unmount mid-capture cannot fire setPieces on a dead component.
    const prunes = new Set<number>();

    const advance = () => {
      const idx = stepRef.current;
      if (idx >= LINE.length) {
        // let the final position breathe, then rebuild the tableau
        timer = window.setTimeout(() => {
          piecesRef.current = initialPieces();
          setPieces(piecesRef.current);
          setTrails([]);
          stepRef.current = 0;
          timer = window.setTimeout(advance, 1600);
        }, 2600);
        return;
      }
      const moves = LINE[idx];
      stepRef.current += 1;

      const next = piecesRef.current.map((p) => ({ ...p, moving: false }));
      let capturedAny = false;
      for (const m of moves) {
        const a = sq(m.from);
        const b = sq(m.to);
        const p = next.find((x) => x.f === a.f && x.r === a.r && !x.captured);
        if (!p) continue;
        const victim = next.find((x) => x.f === b.f && x.r === b.r && x !== p && !x.captured);
        if (victim) {
          victim.captured = true;
          capturedAny = true;
        }
        p.f = b.f;
        p.r = b.r;
        p.moving = true;
      }
      piecesRef.current = next;
      setPieces(next);
      if (capturedAny) {
        const prune = window.setTimeout(() => {
          prunes.delete(prune);
          piecesRef.current = piecesRef.current.filter((p) => !p.captured);
          setPieces(piecesRef.current);
        }, 550);
        prunes.add(prune);
      }

      const t: Trail[] = moves.map((m) => {
        const a = sq(m.from);
        const b = sq(m.to);
        const dx = cx(b.f) - cx(a.f);
        const dy = cy(b.r) - cy(a.r);
        return {
          key: ++trailKey.current,
          x: cx(a.f),
          y: cy(a.r),
          len: Math.hypot(dx, dy),
          ang: (Math.atan2(dy, dx) * 180) / Math.PI,
        };
      });
      setTrails((cur) => [...cur.slice(-3), ...t]);

      timer = window.setTimeout(advance, 1300);
    };

    timer = window.setTimeout(advance, 1400);
    return () => {
      window.clearTimeout(timer);
      for (const id of prunes) window.clearTimeout(id);
    };
  }, []);

  return (
    <div
      className="hz-board-wrap"
      style={{ left: '57%', top: '40%', width: '30%' }}
      role="img"
      aria-label="An animated chess board plays through a romantic-era opening line"
    >
      <div className="hz-board-pool" aria-hidden="true" />
      <div className="hz-board-tilt">
        <div className="hz-board" aria-hidden="true">
          {Array.from({ length: 64 }, (_, i) => {
            const f = i % 8;
            const r = 7 - Math.floor(i / 8);
            // a1 (f=0, r=0) is dark: the light class fires on odd sums.
            return (
              <i
                key={i}
                className={`sq ${(f + r) % 2 === 1 ? 'l' : ''}`}
                style={{ left: `${f * 12.5}%`, top: `${(7 - r) * 12.5}%` }}
              />
            );
          })}
          {trails.map((t) => (
            <div
              key={t.key}
              className="hz-move-trail"
              style={{ left: `${t.x}%`, top: `${t.y}%`, width: `${t.len}%`, transform: `rotate(${t.ang}deg)` }}
            />
          ))}
          {pieces.map((p) => (
            <div
              key={p.id}
              className={`hz-piece${p.moving ? ' moving' : ''}${p.captured ? ' captured' : ''}`}
              style={{ left: `${p.f * 12.5}%`, top: `${(7 - p.r) * 12.5}%` }}
            >
              <PieceIcon kind={p.kind} color={p.color} />
            </div>
          ))}
          <div className="hz-sheen" />
        </div>
      </div>
      {/* the scene veil, re-laid over the board so it sits *in* the light */}
      <div className="hz-board-veil" aria-hidden="true" />
    </div>
  );
}

/**
 * Ambient shooting-light streaks for the hero and finale skies. Positions
 * are % of the art box; each streak gets a deterministic duration/delay
 * spread so the two bands never pulse in sync.
 */
export function Streaks({ count = 3, seed = 0 }: { count?: number; seed?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => {
        const k = i + seed;
        return (
          <div
            key={k}
            className="hz-streak"
            aria-hidden="true"
            style={
              {
                left: `${10 + ((k * 27) % 62)}%`,
                top: `${8 + ((k * 13) % 24)}%`,
                '--dur': `${7 + ((k * 2.3) % 5)}s`,
                '--delay': `${(k * 2.6) % 9}s`,
                '--ang': `${-12 - ((k * 7) % 14)}deg`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </>
  );
}
