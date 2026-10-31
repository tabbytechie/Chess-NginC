/**
 * Canvas effect engine for the landing descent: the ghost-light waterfall
 * streak renderer and the five particle systems (wisp, mote, spray, bubble,
 * shimmer). Framework-agnostic classes driven by one shared rAF ticker; the
 * React wrappers in canvases.tsx mount them and gate on viewport visibility.
 * Palette is the black + green re-skin of the spec's cyan/violet original.
 */

import { themeState } from './theme';

const DPR_CAP = 1.5;
/** jsdom has no matchMedia at all; a missing query always reads "no preference". */
export const mm = (query: string): boolean =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia(query).matches;

export const reduceMotion = () => mm('(prefers-reduced-motion: reduce)');

/* --------------------------------- ticker ---------------------------------- */
type Field = { active: boolean; frame(t: number): void; el: HTMLCanvasElement };

const fields = new Set<Field>();
let rafId = 0;
let last = 0;

function tick(now: number) {
  rafId = 0;
  const t = now / 1000;
  last = now;
  for (const f of fields) {
    if (f.active) f.frame(t);
  }
  if (fields.size && !reduceMotion()) schedule();
  void last;
}

function schedule() {
  // jsdom without pretendToBeVisual has no rAF; the descent simply renders still.
  if (typeof requestAnimationFrame !== 'function') return;
  if (!rafId) rafId = requestAnimationFrame(tick);
}

export function registerField(f: Field): () => void {
  fields.add(f);
  if (!reduceMotion()) schedule();
  return () => {
    fields.delete(f);
    if (!fields.size && rafId) cancelAnimationFrame(rafId);
  };
}

/* --------------------------------- falls ----------------------------------- */

interface Streak {
  x: number;
  len: number;
  speed: number;
  width: number;
  alpha: number;
  phase: number;
  sprite: 0 | 1;
}

function makeSprites(kind: 'ghost' | 'lava', light: boolean): HTMLCanvasElement[] {
  // pre-rendered 8 × 160 vertical gradients, two per kind and per theme:
  // luminous mint streaks at night, white/silver streaks by day (the white
  // theme desaturates the art, so the effects go monochrome with it).
  const grad: [string, string, string][] = light
    ? kind === 'ghost'
      ? [
          ['rgba(255,255,255,0)', 'rgba(255,255,255,.92)', 'rgba(222,232,225,0)'],
          ['rgba(235,242,238,0)', 'rgba(205,218,210,.75)', 'rgba(190,204,196,0)'],
        ]
      : [
          ['rgba(255,255,255,0)', 'rgba(248,252,250,.95)', 'rgba(208,220,213,0)'],
          ['rgba(225,235,229,0)', 'rgba(185,200,191,.8)', 'rgba(160,176,167,0)'],
        ]
    : kind === 'ghost'
      ? [
          ['rgba(185,255,215,0)', 'rgba(215,255,235,.95)', 'rgba(105,215,150,0)'],
          ['rgba(110,220,160,0)', 'rgba(140,235,185,.8)', 'rgba(80,175,120,0)'],
        ]
      : [
          ['rgba(150,255,140,0)', 'rgba(225,255,170,1)', 'rgba(45,190,70,0)'],
          ['rgba(70,200,90,0)', 'rgba(125,245,140,.9)', 'rgba(30,150,55,0)'],
        ];
  const stops = kind === 'ghost' ? [0, 0.35, 1] : [0, 0.5, 1];
  return grad.map((colors) => {
    const c = document.createElement('canvas');
    c.width = 8;
    c.height = 160;
    const ctx = c.getContext('2d');
    if (ctx) {
      const lg = ctx.createLinearGradient(0, 0, 0, 160);
      lg.addColorStop(stops[0], colors[0]);
      lg.addColorStop(stops[1], colors[1]);
      lg.addColorStop(stops[2], colors[2]);
      ctx.fillStyle = lg;
      ctx.fillRect(0, 0, 8, 160);
    }
    return c;
  });
}

const spriteCache: Record<string, HTMLCanvasElement[]> = {};

/** seam water bodies: an opaque column the streaks flow inside */
const BODY_STOPS: Record<'dark' | 'light', [number, string][]> = {
  dark: [
    [0, 'rgba(60,190,120,0)'],
    [0.18, 'rgba(90,225,150,.7)'],
    [0.5, 'rgba(180,250,215,.96)'],
    [0.82, 'rgba(90,225,150,.7)'],
    [1, 'rgba(60,190,120,0)'],
  ],
  light: [
    [0, 'rgba(200,212,205,0)'],
    [0.18, 'rgba(226,236,230,.55)'],
    [0.5, 'rgba(255,255,255,.95)'],
    [0.82, 'rgba(226,236,230,.55)'],
    [1, 'rgba(200,212,205,0)'],
  ],
};

export class FallField implements Field {
  active = true;
  private ctx: CanvasRenderingContext2D | null;
  private streaks: Streak[] = [];
  private w = 0;
  private h = 0;
  private sprites: HTMLCanvasElement[] = [];
  private light = false;

  constructor(
    public el: HTMLCanvasElement,
    private kind: 'ghost' | 'lava',
    private speed: number,
    /** seam canvases pre-fill a water body so the stream reads continuous */
    private body = false,
  ) {
    // jsdom (no canvas package) returns a null 2D context; stay inert there.
    this.ctx = el.getContext('2d');
    if (!this.ctx) return;
    this.light = themeState.light;
    const key = `${kind}-${this.light ? 'l' : 'd'}`;
    if (!spriteCache[key]) spriteCache[key] = makeSprites(kind, this.light);
    this.sprites = spriteCache[key];
    this.resize();
  }

  /** offsetWidth/Height ignore transforms, so load zoom can't distort sizing */
  resize() {
    const ctx = this.ctx;
    if (!ctx) return;
    const w = this.el.offsetWidth;
    const h = this.el.offsetHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
    this.el.width = Math.max(1, Math.round(w * dpr));
    this.el.height = Math.max(1, Math.round(h * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = w;
    this.h = h;
    this.build();
    if (reduceMotion()) this.frame(0);
  }

  private build() {
    const n =
      this.kind === 'ghost'
        ? Math.round(this.w / 2.2) * 2
        : Math.round(this.w / 3) * 3;
    const rnd = (a: number, b: number) => a + Math.random() * (b - a);
    this.streaks = Array.from({ length: Math.max(0, n) }, () => ({
      x: this.kind === 'ghost' ? rnd(0, this.w) : rnd(this.w * 0.25, this.w * 0.75),
      len: this.kind === 'ghost' ? rnd(60, 280) : rnd(30, 100),
      speed:
        this.kind === 'ghost' ? rnd(420, 760) * this.speed : rnd(195, 350) * this.speed,
      width: this.kind === 'ghost' ? rnd(0.8, 4) : rnd(1, 3.2),
      alpha: rnd(0.18, 0.73),
      phase: rnd(0, 2000),
      sprite: (Math.random() < 0.45 ? 0 : 1) as 0 | 1,
    }));
  }

  frame(t: number) {
    const ctx = this.ctx;
    if (!ctx) return;
    const { w, h } = this;
    if (!w || !h) return;
    ctx.clearRect(0, 0, w, h);
    if (this.body) {
      const lg = ctx.createLinearGradient(0, 0, w, 0);
      for (const [stop, color] of BODY_STOPS[this.light ? 'light' : 'dark']) lg.addColorStop(stop, color);
      ctx.fillStyle = lg;
      ctx.fillRect(0, 0, w, h);
    }
    ctx.globalCompositeOperation = 'lighter';
    for (const s of this.streaks) {
      const span = h + s.len;
      const y = ((t * s.speed + s.phase) % span) - s.len;
      let a = s.alpha;
      if (this.kind === 'ghost') a *= 1 - ((Math.abs(s.x / w - 0.5) * 2) ** 2) * 0.6;
      ctx.globalAlpha = Math.max(0, a);
      const spr = this.sprites[s.sprite];
      ctx.drawImage(spr, s.x - s.width / 2, y, s.width, s.len);
      ctx.drawImage(spr, s.x - s.width / 2, y + span, s.width, s.len);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }
}

/* -------------------------------- particles -------------------------------- */

interface Particle {
  u: number;
  v: number;
  r: number;
  phase: number;
  speed: number;
}

function makeParticles(count: number): Particle[] {
  const rnd = (a: number, b: number) => a + Math.random() * (b - a);
  return Array.from({ length: count }, () => ({
    u: Math.random(),
    v: Math.random(),
    r: Math.random(),
    phase: rnd(0, Math.PI * 2),
    speed: rnd(0.4, 1.2),
  }));
}

export class DustField implements Field {
  active = true;
  private ctx: CanvasRenderingContext2D | null;
  private parts: Particle[];
  private w = 0;
  private h = 0;
  /** particle RGB triplets picked for the theme at construction time */
  private c: string;
  private c2: string;
  private cHi: string;

  constructor(
    public el: HTMLCanvasElement,
    private kind: 'wisp' | 'mote' | 'spray' | 'bubble' | 'shimmer',
    count: number,
    /** % box restricting the particles, from data-x/y/w/h */
    private box?: { x: number; y: number; w: number; h: number },
  ) {
    const light = themeState.light;
    // wisp / mote / spray share c; bubbles use c→c2 with a cHi highlight;
    // shimmer draws c lines. Day theme is white silver: the effects must read
    // as light on the desaturated art, never as colour.
    this.c = light ? '172,188,179' : '185,245,205';
    this.c2 = light ? '210,222,215' : '110,230,140';
    this.cHi = light ? '255,255,255' : '240,255,235';
    if (kind === 'mote') this.c = light ? '158,175,166' : '165,235,195';
    if (kind === 'spray') this.c = light ? '235,242,238' : '200,250,220';
    if (kind === 'bubble') this.c = light ? '245,250,247' : '220,255,190';
    if (kind === 'shimmer') this.c = light ? '150,168,158' : '225,255,205';
    this.ctx = el.getContext('2d');
    this.parts = makeParticles(count);
    if (this.ctx) this.resize();
  }

  resize() {
    const ctx = this.ctx;
    if (!ctx) return;
    const w = this.el.offsetWidth;
    const h = this.el.offsetHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
    this.el.width = Math.max(1, Math.round(w * dpr));
    this.el.height = Math.max(1, Math.round(h * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = w;
    this.h = h;
    if (reduceMotion()) this.frame(0);
  }

  private boxRect() {
    if (!this.box) return { x: 0, y: 0, w: this.w, h: this.h };
    return {
      x: (this.box.x / 100) * this.w,
      y: (this.box.y / 100) * this.h,
      w: (this.box.w / 100) * this.w,
      h: (this.box.h / 100) * this.h,
    };
  }

  frame(t: number) {
    const ctx = this.ctx;
    if (!ctx) return;
    if (!this.w || !this.h) return;
    ctx.clearRect(0, 0, this.w, this.h);
    const b = this.boxRect();
    switch (this.kind) {
      case 'wisp':
        this.drawWisps(t, b);
        break;
      case 'mote':
        this.drawMotes(t, b);
        break;
      case 'spray':
        this.drawSpray(t, b);
        break;
      case 'bubble':
        this.drawBubbles(t, b);
        break;
      case 'shimmer':
        this.drawShimmer(t, b);
        break;
    }
  }

  private dot(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  /** hero: rises from the canyon floor, respawns once past 35 % height */
  private drawWisps(t: number, b: Box) {
    const ctx = this.ctx!;
    for (const p of this.parts) {
      const loop = 0.63; // travels v .98 → .35 then respawns
      const rise = (t * 0.02 * p.speed + p.phase * 0.16) % loop;
      const v = 0.98 - rise;
      const y = b.y + (1 - v) * b.h;
      const sway = Math.sin(0.8 * t * p.speed + p.phase) * 0.012 * this.w;
      const x = b.x + (0.2 + p.u * 0.6) * b.w + sway;
      const fade = Math.min(1, rise / (loop * 0.25) + 0.2);
      const pulse = Math.abs(Math.sin(2 * t + p.phase));
      const a = fade * (0.25 + 0.6 * pulse);
      this.dot(ctx, x, y, 0.8 + p.r * 1.8, `rgba(${this.c},${a.toFixed(3)})`);
    }
  }

  /** crypt: drift up very slowly, wrap, sway */
  private drawMotes(t: number, b: Box) {
    const ctx = this.ctx!;
    for (const p of this.parts) {
      const v = ((p.v - t * 0.008 * p.speed) % 1 + 1) % 1;
      const x = b.x + p.u * b.w + Math.sin(0.5 * t * p.speed + p.phase) * 0.02 * this.w;
      const y = b.y + (1 - v) * b.h;
      const a = 0.25 + p.r * 0.5;
      this.dot(ctx, x, y, 0.6 + p.r * 1.4, `rgba(${this.c},${a.toFixed(3)})`);
    }
  }
  /** mill: thrown sideways where the falls hit the wheel, parabolic fall */
  private drawSpray(t: number, b: Box) {
    const ctx = this.ctx!;
    for (const p of this.parts) {
      const life = (t * p.speed * 0.8 + p.phase) % 1;
      const x = b.x + (p.u + (p.r - 0.5) * 0.6 * life) * b.w;
      const y = b.y + life * life * 0.9 * b.h;
      const a = Math.max(0, 1 - life);
      this.dot(ctx, x, y, 0.7 + p.r * 1.6, `rgba(${this.c},${a.toFixed(3)})`);
    }
  }

  /** cauldron: bubbles rise through the box wobbling, radial gradient + highlight */
  private drawBubbles(t: number, b: Box) {
    const ctx = this.ctx!;
    const scale = this.w / 1440;
    for (const p of this.parts) {
      const life = (t * p.speed * 0.16 + p.phase) % 1;
      const x = b.x + p.u * b.w + Math.sin(1.4 * t + p.phase) * 0.03 * b.w;
      const y = b.y + (1 - life) * b.h;
      const r = (2 + p.r * 7) * Math.max(scale, 0.55);
      const a = Math.sin(life * Math.PI) * 0.9;
      if (a <= 0.01) continue;
      const rg = ctx.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, `rgba(${this.c},${a})`);
      rg.addColorStop(0.55, `rgba(${this.c2},${0.55 * a})`);
      rg.addColorStop(1, `rgba(${this.c2},0)`);
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = `rgba(${this.cHi},${a * 0.8})`;
      ctx.beginPath();
      ctx.arc(x - r * 0.35, y - r * 0.35, Math.max(0.6, r * 0.18), 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /** lake: horizontal glints on the moon's light pillar, wider further down */
  private drawShimmer(t: number, b: Box) {
    const ctx = this.ctx!;
    for (const p of this.parts) {
      const a = Math.max(0, Math.sin(t * (1.2 + 2 * p.r) + p.phase)) * 0.8;
      if (a <= 0.02) continue;
      const depth = p.v;
      const spread = 0.3 + depth * 0.7;
      const x = b.x + (0.5 + (p.u - 0.5) * spread) * b.w;
      const y = b.y + depth * b.h;
      const len = 12 + p.r * 20;
      ctx.fillStyle = `rgba(${this.c},${a.toFixed(3)})`;
      ctx.fillRect(x - len / 2, y, len, 1.2);
    }
  }
}

type Box = { x: number; y: number; w: number; h: number };
