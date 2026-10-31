/**
 * Static data for the landing descent: Higgsfield art URLs (served through
 * the images.higgs.ai resizer), sprite-sheet crops and the exact overlay
 * placements, ported from the Hollowmere scroll spec and recolored to the
 * Chess NginC black + green theme. Positions are % of the art box.
 */

import type { CSSProperties } from 'react';

const HF = (encoded: string, w = 2400) =>
  `https://images.higgs.ai/?default=1&output=webp&url=${encoded}&w=${w}&q=85`;

export const SCENES = {
  hero: HF(
    'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023809_d6836117-c958-4680-aa43-1e1973fbc17c.png',
  ),
  crypt: HF(
    'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023812_40e3f5f5-a613-4a33-9c78-4cab8b04a992.png',
  ),
  mill: HF(
    'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023814_b2c8f33a-3c90-4aa1-bb91-cce7f0deb878.png',
  ),
  foundry: HF(
    'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023817_3e21faea-ad1c-4723-be92-9b22692094e1.png',
  ),
  lake: HF(
    'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023819_5b21be3d-159e-4d1d-a3b3-80339bc5d5f1.png',
  ),
} as const;

export const SEAMS = [
  {
    img: HF(
      'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_025938_e54c50c3-9748-4d00-af68-886bef6e65e7.png',
    ),
    focus: 48,
    // left / top / width / height in % of the band, plus stream speed.
    fall: { l: 44.8, t: 2, w: 10.4, h: 90, speed: 1, kind: 'ghost' },
  },
  {
    img: HF(
      'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_030022_7a86d576-94d5-4069-b515-62547af3b50c.png',
    ),
    focus: 40,
    fall: { l: 21.4, t: 22, w: 10.6, h: 74, speed: 1, kind: 'ghost' },
  },
  {
    img: HF(
      'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_025940_a85237c9-d7e3-4c28-b1d9-71ad7d8cbca4.png',
    ),
    focus: 66,
    fall: { l: 60.8, t: 46, w: 13.6, h: 50, speed: 1, kind: 'ghost' },
  },
  {
    img: HF(
      'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_025942_debc2172-5187-4ad4-af0d-307c5e0277b5.png',
    ),
    focus: 45,
    fall: null,
  },
] as const;

export const SHEET_URL = HF(
  'https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20261029_023917_156ac3d3-e103-4a95-947d-07554914ab0b.png',
  1024,
);

/** sheet is 1024 × 688 */
export const SPRITES = {
  ghost1: { x: 39, y: 103, w: 204, h: 221 },
  ghost2: { x: 303, y: 122, w: 152, h: 212 },
  ghost3: { x: 538, y: 125, w: 208, h: 201 },
  ghost4: { x: 833, y: 70, w: 131, h: 280 },
  batUp: { x: 41, y: 389, w: 203, h: 221 },
  batDown: { x: 299, y: 389, w: 195, h: 221 },
} as const;

export type SpriteName = keyof typeof SPRITES;

/** background-size / position / aspect-ratio math for one sheet crop. */
export function spriteStyle(name: SpriteName): CSSProperties {
  const s = SPRITES[name];
  return {
    backgroundImage: `url('${SHEET_URL}')`,
    backgroundSize: `${(1024 / s.w) * 100}% ${(688 / s.h) * 100}%`,
    backgroundPosition: `${(s.x / (1024 - s.w)) * 100}% ${(s.y / (688 - s.h)) * 100}%`,
    aspectRatio: `${s.w} / ${s.h}`,
  };
}

export interface Glow {
  l: number;
  t: number;
  w: number;
  kind?: 'warm' | 'cold';
}

export interface Mist {
  l: number;
  t: number;
  w: number;
  h: number;
}

export interface FallBox {
  l: number;
  t: number;
  w: number;
  h: number;
  speed: number;
  kind: 'ghost' | 'lava';
}

export interface DustSpec {
  kind: 'wisp' | 'mote' | 'spray' | 'bubble' | 'shimmer';
  count: number;
  /** optional % box restricting where particles live */
  box?: { x: number; y: number; w: number; h: number };
}

export interface GhostSpec {
  sprite: SpriteName;
  l: number;
  t: number;
  w: number;
}

export interface SceneSpec {
  id: string;
  img: string;
  focus: number;
  falls: FallBox[];
  mists: Mist[];
  moonglow?: Glow;
  glows: Glow[];
  dust: DustSpec[];
  ghosts: GhostSpec[];
  /** number of bats crossing the sky; 0 = none */
  bats: number;
}

const g = (l: number, t: number, w: number, kind: Glow['kind'] = 'warm'): Glow => ({
  l,
  t,
  w,
  kind,
});

export const HERO: SceneSpec = {
  id: 'top',
  img: SCENES.hero,
  focus: 50,
  falls: [
    { l: 47.4, t: 51, w: 5.6, h: 22, speed: 1, kind: 'ghost' },
    { l: 44, t: 80, w: 12.4, h: 34, speed: 1.15, kind: 'ghost' },
  ],
  mists: [{ l: 50, t: 73, w: 22, h: 9 }],
  moonglow: { l: 50.2, t: 25.6, w: 21 },
  glows: [
    g(4.8, 54.4, 4.6),
    g(18.5, 50.6, 3.6),
    g(17.5, 69.4, 3.8),
    g(25.9, 38.3, 2.6),
    g(31.6, 42, 2.4),
    g(30.4, 63, 2.4),
    g(80, 36.7, 3),
    g(85, 45.3, 3),
    g(93.8, 53, 4.6),
    g(87.8, 73, 3.8),
    g(74.5, 61, 2.6),
    g(67.2, 64.8, 2.6),
  ],
  dust: [{ kind: 'wisp', count: 70 }],
  ghosts: [
    { sprite: 'ghost1', l: 21, t: 30, w: 4.2 },
    { sprite: 'ghost2', l: 78, t: 21, w: 3.4 },
    { sprite: 'ghost4', l: 64, t: 44, w: 2.8 },
    { sprite: 'ghost3', l: 36, t: 46, w: 2.4 },
  ],
  bats: 4,
};

export const PLAY: SceneSpec = {
  id: 'play',
  img: SCENES.crypt,
  focus: 48,
  falls: [{ l: 40.6, t: 0, w: 17.2, h: 90, speed: 0.9, kind: 'ghost' }],
  mists: [{ l: 49, t: 84, w: 34, h: 14 }],
  glows: [
    g(20.3, 69.8, 7, 'cold'),
    g(72.5, 19, 5, 'cold'),
    g(80.4, 18.1, 4.4, 'cold'),
    g(76, 41.6, 5.6, 'cold'),
    g(85, 43.3, 4, 'cold'),
    g(70.5, 68.5, 4.4, 'cold'),
    g(77.3, 63.7, 4.4, 'cold'),
    g(85.3, 66.3, 4, 'cold'),
    g(7.6, 85, 4.4),
    g(13.2, 87, 3.2),
    g(92.2, 84, 3.6),
  ],
  dust: [{ kind: 'mote', count: 50 }],
  ghosts: [{ sprite: 'ghost4', l: 30, t: 22, w: 2.6 }],
  bats: 0,
};

export const IMPROVE: SceneSpec = {
  id: 'improve',
  img: SCENES.mill,
  focus: 40,
  falls: [{ l: 19.5, t: 0, w: 18, h: 38, speed: 1.05, kind: 'ghost' }],
  mists: [{ l: 31, t: 33, w: 22, h: 10 }],
  glows: [
    g(12, 34, 4.2),
    g(37.5, 47.7, 4.2),
    g(32.3, 52.6, 4.2),
    g(11.7, 62.3, 4.2),
    g(39, 78.2, 4.2),
    g(64.5, 70.3, 9, 'cold'),
    g(88.5, 70.7, 9, 'cold'),
    g(61.4, 75, 2.4),
    g(72.6, 75.4, 2.4),
    g(91.5, 75.4, 2.4),
  ],
  dust: [{ kind: 'spray', count: 60, box: { x: 20, y: 30, w: 20, h: 18 } }],
  ghosts: [],
  bats: 0,
};

export const LEARN: SceneSpec = {
  id: 'learn',
  img: SCENES.foundry,
  focus: 66,
  falls: [{ l: 67.4, t: 0, w: 11.8, h: 37, speed: 1, kind: 'ghost' }],
  mists: [],
  glows: [g(70, 93, 26), g(16.8, 78.2, 6), g(27.8, 85.3, 4), g(18, 66.3, 8), g(73, 33, 14, 'cold')],
  dust: [
    { kind: 'bubble', count: 22, box: { x: 60, y: 8, w: 24, h: 28 } },
  ],
  ghosts: [],
  bats: 0,
};

/** three lava streams pouring from the painted pipes of scene 4 */
export const LEARN_LAVA: FallBox[] = [
  { l: 62.3, t: 66.5, w: 1.8, h: 25, speed: 0.55, kind: 'lava' },
  { l: 69.4, t: 66.5, w: 1.8, h: 25, speed: 0.6, kind: 'lava' },
  { l: 76.5, t: 66.5, w: 1.8, h: 25, speed: 0.5, kind: 'lava' },
];

export const FINALE: SceneSpec = {
  id: 'compete',
  img: SCENES.lake,
  focus: 45,
  falls: [],
  mists: [],
  moonglow: { l: 39.1, t: 56.6, w: 19 },
  glows: [
    g(29.9, 76.7, 3.4),
    g(32.9, 72.7, 2.4),
    g(45.9, 72.7, 2.4),
    g(48.3, 77.4, 3.6),
    g(55.4, 81.8, 4),
    g(58.1, 75.6, 3.2),
    g(53.9, 72.2, 2.2),
    g(62.5, 72.5, 2.2),
    g(69.9, 80.9, 4),
    g(74.9, 75.9, 3.2),
    g(73, 72.3, 2.2),
    g(79.1, 72.5, 2.2),
    g(24.8, 72.1, 2.2),
    g(7.8, 65.4, 5),
    g(89.8, 76.9, 5),
  ],
  dust: [{ kind: 'shimmer', count: 90, box: { x: 34, y: 69, w: 10, h: 22 } }],
  ghosts: [
    { sprite: 'ghost2', l: 66, t: 26, w: 3 },
    { sprite: 'ghost1', l: 27, t: 38, w: 2.6 },
  ],
  bats: 3,
};

export const SCENE_ORDER: SceneSpec[] = [HERO, PLAY, IMPROVE, LEARN, FINALE];
