/**
 * Living sprites for the descent: ghosts that bob, wander and shy away from
 * the cursor, and bats flapping across the sky band. Cursor position is a
 * module-level singleton updated once by LandingPage's pointer listener.
 */
import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';

import { spriteStyle } from './data';
import type { GhostSpec, SpriteName } from './data';
import { reduceMotion } from './effects';
import { pointer } from './pointer';

/**
 * One rAF per scene holding ghosts. Each ghost drifts on its own sine wander
 * around its % anchor and is pushed directly away from the cursor within
 * 260px, easing back with 1 − e^(−3·dt).
 */
export function Ghosts({ ghosts, artRef }: { ghosts: GhostSpec[]; artRef: React.RefObject<HTMLDivElement | null> }) {
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    if (reduceMotion()) {
      // one still frame at the anchor position
      return;
    }
    if (typeof requestAnimationFrame !== 'function') return; // bare jsdom
    const state = ghosts.map(() => ({ px: 0, py: 0, t: Math.random() * 100 }));
    let raf = 0;
    let last = performance.now();

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const art = artRef.current;
      if (!art) {
        raf = requestAnimationFrame(loop);
        return;
      }
      const rect = art.getBoundingClientRect();
      if (rect.bottom < -60 || rect.top > window.innerHeight + 60) {
        raf = requestAnimationFrame(loop);
        return;
      }
      ghosts.forEach((g, i) => {
        const el = refs.current[i];
        if (!el) return;
        const s = state[i];
        s.t += dt;
        const ax = rect.left + (g.l / 100) * rect.width;
        const ay = rect.top + (g.t / 100) * rect.height;
        const wanderX = Math.sin(0.35 * s.t + i * 1.7) * 0.012 * rect.width;
        const wanderY = Math.sin(0.9 * s.t + i * 2.3) * 0.014 * rect.height;
        const cx = ax + wanderX + s.px;
        const cy = ay + wanderY + s.py;
        const dx = cx - pointer.x;
        const dy = cy - pointer.y;
        const d = Math.hypot(dx, dy);
        let tx = wanderX;
        let ty = wanderY;
        if (d < 260 && d > 0.001) {
          const push = (1 - d / 260) ** 1.5 * 90;
          s.px += ((dx / d) * push - s.px) * (1 - Math.exp(-3 * dt));
          s.py += ((dy / d) * push - s.py) * (1 - Math.exp(-3 * dt));
          tx += s.px;
          ty += s.py;
        } else {
          s.px *= Math.exp(-3 * dt);
          s.py *= Math.exp(-3 * dt);
          tx += s.px;
          ty += s.py;
        }
        const rot = Math.sin(0.7 * s.t + i) * 6 + tx * 0.05;
        el.style.transform = `translate3d(calc(-50% + ${tx.toFixed(1)}px), calc(-50% + ${ty.toFixed(1)}px), 0) rotate(${rot.toFixed(2)}deg)`;
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [ghosts, artRef]);

  return (
    <>
      {ghosts.map((g, i) => (
        <div
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          className="hz-sprite hz-ghost"
          style={{
            left: `${g.l}%`,
            top: `${g.t}%`,
            width: `${g.w}%`,
            ...spriteStyle(g.sprite),
          }}
          aria-hidden="true"
        />
      ))}
    </>
  );
}

/**
 * Bats fly the full sky band left→right on CSS keyframes with per-bat
 * duration/delay; the inner element bobs on a second keyframe and the
 * wing frames alternate via the .down overlay's opacity steps animation.
 */
export function Bats({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => {
        const dur = 9 + ((i * 3.7) % 7); // deterministic 9–16s
        const y0 = 8 + ((i * 6.3) % 26); // sky band 8–34 %
        const size = 1.6 + ((i * 1.31) % 1.6); // % of art width
        const outer: CSSProperties = {
          left: 0,
          top: `${y0}%`,
          width: `${size}%`,
          aspectRatio: '203 / 221',
          animation: `hz-fly ${dur}s linear infinite`,
          animationDelay: `${-i * dur * 0.31}s`,
        };
        return (
          <div key={i} className="hz-sprite hz-bat-wrap" style={outer} aria-hidden="true">
            <div
              className="hz-bat"
              style={{
                position: 'relative',
                width: '100%',
                aspectRatio: '203 / 221',
                transform: 'none',
                animation: `hz-bob ${2.2 + (i % 3)}s ease-in-out infinite`,
              }}
            >
              <BatFrame sprite="batUp" />
              <BatFrame sprite="batDown" down />
            </div>
          </div>
        );
      })}
    </>
  );
}

function BatFrame({ sprite, down }: { sprite: SpriteName; down?: boolean }) {
  return <div className={`frame${down ? ' down' : ''}`} style={spriteStyle(sprite)} />;
}
