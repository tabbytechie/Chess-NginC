/**
 * The marketing landing page: one continuous illustrated descent (five
 * full-bleed scenes joined by drawn rock seams) recolored to the Chess
 * NginC black + green theme. Copy mirrors the in-app words — "Play online",
 * "Learn", "Achievements", "Move-by-move classification", "play the
 * position, not the clock". Motion lives in motion.ts / effects.ts; this
 * file only assembles the picture and the words.
 */
import { useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';

import './landing.css';
import { DustCanvas, FallCanvas } from './canvases';
import { Bats, Ghosts } from './sprites';
import { BoardFeature, Streaks } from './board';
import { loadLandingTheme, setLandingTheme } from './theme';
import {
  FINALE,
  HERO,
  IMPROVE,
  LEARN,
  LEARN_LAVA,
  PLAY,
  SEAMS,
} from './data';
import type { Glow, SceneSpec } from './data';
import {
  useAnchorScroll,
  useDescent,
  useIntro,
  useResponsiveArt,
  useReveals,
} from './motion';

/** one masked rising line of copy */
function Ln({ tag = 'p', children }: { tag?: 'h2' | 'h3' | 'p'; children: ReactNode }) {
  const Tag = tag;
  return (
    <Tag className="ln">
      <span>{children}</span>
    </Tag>
  );
}

function GlowDot({ glow }: { glow: Glow }) {
  return (
    <div
      className={`hz-glow ${glow.kind ?? 'warm'}`}
      style={{ left: `${glow.l}%`, top: `${glow.t}%`, width: `${glow.w}%` }}
      aria-hidden="true"
    />
  );
}

function Logo() {
  // the app's knight on the spec's white triangle, plus the "Chess NginC"
  // wordmark so the brand is spelled out on the landing nav; both halves
  // follow the landing theme tokens and read on night and day alike.
  return (
    <a
      href="#top"
      className="hz-logo inline-flex items-center gap-2 text-[13px] font-semibold tracking-[0.14em] uppercase"
      style={{ color: 'var(--ink)' }}
      aria-label="Chess NginC home"
    >
      <svg width="34" height="32" viewBox="0 0 26 24" aria-hidden="true">
        <polygon points="13,1 25,23 1,23" fill="var(--ink)" />
        <text x="13" y="21" textAnchor="middle" fontSize="15" fill="var(--night)">
          ♞
        </text>
      </svg>
      <span>Chess NginC</span>
    </a>
  );
}

function Nav({ light, onToggleTheme }: { light: boolean; onToggleTheme: () => void }) {
  return (
    <header className="hz-nav" aria-label="landing">
      <nav className="hide-mobile flex gap-[5.6vw]" aria-label="primary">
        <a className="hz-navlink" href="#play">
          Play online
        </a>
        <a className="hz-navlink" href="#improve">
          Reviews
        </a>
        <a className="hz-navlink" href="#learn">
          Learn
        </a>
      </nav>
      <div className="flex justify-center">
        <Logo />
      </div>
      <div className="flex items-center justify-end gap-4">
        <a className="hz-navlink hide-mobile" href="#compete">
          Achievements
        </a>
        <Link to="/login" className="hz-navlink hide-mobile">
          Log in
        </Link>
        <button
          type="button"
          className="hz-theme-toggle"
          onClick={onToggleTheme}
          aria-label={light ? 'Switch to night mode' : 'Switch to day mode'}
          title={light ? 'Night' : 'Day'}
        >
          {light ? <Moon size={15} /> : <Sun size={15} />}
        </button>
        <Link to="/register" className="tickets">
          Sign up
        </Link>
      </div>
    </header>
  );
}

function Scene({
  spec,
  hero = false,
  artRef,
  children,
}: {
  spec: SceneSpec;
  hero?: boolean;
  artRef?: React.RefObject<HTMLDivElement | null>;
  children?: ReactNode;
}) {
  return (
    <section id={spec.id} className={`hz-scene${hero ? ' hero' : ''}`}>
      <div className="hz-art" data-focus={spec.focus} style={{ '--img': `url('${spec.img}')` } as React.CSSProperties} ref={artRef}>
        <div className="bg" aria-hidden="true" />
        {spec.moonglow && (
          <div
            className="hz-moonglow"
            style={{ left: `${spec.moonglow.l}%`, top: `${spec.moonglow.t}%`, width: `${spec.moonglow.w}%` }}
            aria-hidden="true"
          />
        )}
        {spec.falls.map((f, i) => (
          <FallCanvas key={i} spec={f} />
        ))}
        {spec.mists.map((m, i) => (
          <div
            key={i}
            className="hz-mist"
            style={{ left: `${m.l}%`, top: `${m.t}%`, width: `${m.w}%`, height: `${m.h}%` }}
            aria-hidden="true"
          />
        ))}
        {spec.glows.map((glow, i) => (
          <GlowDot key={i} glow={glow} />
        ))}
        {spec.dust.map((d, i) => (
          <DustCanvas key={i} spec={d} />
        ))}
        <Ghosts ghosts={spec.ghosts} artRef={artRef ?? { current: null }} />
        {spec.bats > 0 && <Bats count={spec.bats} />}
        {children}
      </div>
    </section>
  );
}

function Seam({ seam }: { seam: (typeof SEAMS)[number] }) {
  return (
    <div className="hz-seam" aria-hidden="true">
      <div className="band" data-focus={seam.focus}>
        {seam.fall && <FallCanvas spec={seam.fall} body />}
        <img src={seam.img} alt="" loading="eager" />
      </div>
    </div>
  );
}

function CopyBlock({
  left,
  top,
  width,
  children,
  finale = false,
}: {
  left?: string;
  top: string;
  width?: string;
  children: ReactNode;
  finale?: boolean;
}) {
  const style: React.CSSProperties = { position: 'absolute', left, top, width, maxWidth: 520, zIndex: 6 };
  if (finale) {
    style.left = '50%';
    style.transform = 'translateX(-50%)';
    style.width = '60%';
    style.maxWidth = 'none';
    style.textAlign = 'center';
  }
  return (
    <div className={`hz-copy${finale ? ' finale' : ''}`} style={style}>
      {children}
    </div>
  );
}

export default function LandingPage() {
  const [light, setLight] = useState(loadLandingTheme);
  // themeState is hydrated at module import from localStorage, so canvas
  // effects already see the correct palette on first mount. A flip writes
  // the singleton synchronously (before setLight schedules the re-render)
  // so the remounted subtree's child effects read the new value.
  const themeKey = light ? 'day' : 'night';
  const toggleTheme = () => {
    const next = !light;
    setLandingTheme(next);
    setLight(next);
  };

  const rootRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const heroArtRef = useRef<HTMLDivElement>(null);
  const heroCopyRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const lampRef = useRef<HTMLDivElement>(null);
  // stable across renders: motion hooks only re-attach when the canvas
  // subtree remounts (themeKey), never because a fresh refs object landed.
  const refs = useMemo(
    () => ({
      root: rootRef,
      scroller: scrollerRef,
      heroArt: heroArtRef,
      heroCopy: heroCopyRef,
      title: titleRef,
      lamp: lampRef,
    }),
    [],
  );

  useDescent(refs, themeKey);
  useIntro(refs, themeKey);
  useReveals(scrollerRef, themeKey);
  useAnchorScroll(scrollerRef);
  useResponsiveArt(rootRef, themeKey);

  const title = 'CHESS NGINC';

  return (
    <div className={`hz-landing${light ? ' light' : ''}`} ref={rootRef}>
      <Nav light={light} onToggleTheme={toggleTheme} />

      {/* remounting the canvas subtree on a theme flip rebuilds every field
          with the other palette — streaks, particles and seam bodies included */}
      <div key={light ? 'day' : 'night'} ref={scrollerRef} style={{ position: 'fixed', top: 0, left: 0, width: '100%' }}>
        {/* 1 — hero: the moonlit arena */}
        <Scene spec={HERO} hero artRef={heroArtRef}>
          <Streaks count={4} />
          <div className="hz-hero-copy" ref={heroCopyRef} style={{ top: 'calc(var(--artH) * .085)' }}>
            <h1 ref={titleRef} className="hz-title" aria-label={title}>
              {title.split('').map((ch, i) => (
                <span key={i} className="letter" aria-hidden="true">
                  <span>{ch === ' ' ? '\u00A0' : ch}</span>
                </span>
              ))}
            </h1>
            <p className="hz-sub" style={{ top: 'calc(var(--artH) * .335)' }}>
              PLAY · IMPROVE · COMPETE
            </p>
          </div>
        </Scene>

        <Seam seam={SEAMS[0]} />

        {/* 2 — the crypt: play, with the floating board */}
        <Scene spec={PLAY}>
          <BoardFeature />
          <CopyBlock left="6.5%" top="26%" width="31%">
            <Ln tag="h2">Play the Position</Ln>
            <div className="hz-rule" aria-hidden="true" />
            <Ln>
              One board, every opponent. Face Stockfish at any strength — from a patient club
              partner to full grandmaster depth — or sit down against a friend in a live game
              with clocks, moves and all.
            </Ln>
            <Ln>
              Every game is saved, replayable and ready for review. Play the position, not the
              clock.
            </Ln>
            <Link to="/lobby" className="hz-btn">
              Play online
            </Link>
          </CopyBlock>
        </Scene>

        <Seam seam={SEAMS[1]} />

        {/* 3 — the mill: reviews */}
        <Scene spec={IMPROVE}>
          <CopyBlock left="55%" top="24%" width="40%">
            <Ln tag="h2">Improve Every Game</Ln>
            <div className="hz-rule" aria-hidden="true" />
            <Ln tag="h3">The Game Review.</Ln>
            <Ln>
              Finish a game and the engine turns it over move by move: blunders, mistakes and
              best play, an evaluation curve across the whole game, and the moment each turn
              was decided.
            </Ln>
            <Ln tag="h3">The Coach.</Ln>
            <Ln>
              Ask the coach about any position and it answers in plain words, grounded in your
              own games and the opening book — and it will read the lesson aloud in a voice you
              choose.
            </Ln>
          </CopyBlock>
        </Scene>

        <Seam seam={SEAMS[2]} />

        {/* 4 — the foundry: training */}
        <Scene spec={LEARN}>
          {LEARN_LAVA.map((f, i) => (
            <FallCanvas key={i} spec={f} />
          ))}
          <CopyBlock left="6.5%" top="25%" width="40%">
            <Ln tag="h2">Train With Intent</Ln>
            <div className="hz-rule" aria-hidden="true" />
            <Ln tag="h3">Drills at the Ready.</Ln>
            <Ln>
              Puzzles, openings and endgame lines poured straight from your own games — the
              weaknesses the review found, worked until they are strengths.
            </Ln>
            <Ln tag="h3">Every Milestone Earned.</Ln>
            <Ln>
              Points, streaks and achievements track the climb. First checkmate, first 1500,
              the long castling run — each one lights up when you earn it.
            </Ln>
          </CopyBlock>
        </Scene>

        <Seam seam={SEAMS[3]} />

        {/* 5 — the lake: the invite */}
        <Scene spec={FINALE}>
          <Streaks count={3} seed={5} />
          <CopyBlock top="30%" finale>
            <Ln tag="h2">See you at the board.</Ln>
            <div className="hz-rule mx-auto" aria-hidden="true" />
            <div className="flex items-center justify-center gap-4">
              <Link to="/register" className="hz-btn">
                Sign up
              </Link>
              <Link to="/login" className="hz-btn ghost">
                Log in
              </Link>
            </div>
          </CopyBlock>
        </Scene>
      </div>

      <div ref={lampRef} className="hz-lamp" aria-hidden="true" />
    </div>
  );
}
