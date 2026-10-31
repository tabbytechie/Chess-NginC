/**
 * The landing page's motion system, ported from the Hollowmere scroll spec:
 * eased momentum scrolling over a fixed scroller, hero parallax with the
 * title spreading on descent, the WAAPI load intro, line-by-line section
 * reveals and the warm lantern glow that trails the cursor.
 */
import { useEffect } from 'react';
import type { RefObject } from 'react';

import { pointer } from './pointer';
import { mm } from './effects';

const EASE = 'cubic-bezier(.2,.8,.2,1)';

export interface DescentRefs {
  root: RefObject<HTMLElement | null>;
  scroller: RefObject<HTMLDivElement | null>;
  heroArt: RefObject<HTMLDivElement | null>;
  heroCopy: RefObject<HTMLDivElement | null>;
  title: RefObject<HTMLHeadingElement | null>;
  lamp: RefObject<HTMLDivElement | null>;
}

/** eased momentum scroll + hero parallax + title spread + cursor lamp */
export function useDescent(refs: DescentRefs, themeKey: string): void {
  // The descent is imperative DOM work driven through refs (translate the
  // fixed scroller, parallax the hero, trail the lamp) — exactly what ref
  // boxes are for. The compiler's immutability rule cannot see through the
  // DescentRefs wrapper, so it is scoped off for this effect only.
  /* eslint-disable react-hooks/immutability */
  useEffect(() => {
    const scroller = refs.scroller.current;
    if (!scroller) return;
    if (typeof requestAnimationFrame !== 'function') return; // bare jsdom
    const root = refs.root.current;
    const heroArt = refs.heroArt.current;
    const heroCopy = refs.heroCopy.current;
    const title = refs.title.current;
    const lamp = refs.lamp.current;
    const finePointer = mm('(pointer: fine)');
    const reduced = mm('(prefers-reduced-motion: reduce)');

    const setBodyHeight = () => {
      if (root) root.style.height = `${scroller.offsetHeight}px`;
    };
    setBodyHeight();
    window.addEventListener('resize', setBodyHeight);

    let cur = window.scrollY;
    let raf = 0;
    let last = performance.now();
    let lx = pointer.x;
    let ly = pointer.y;
    if (lamp) lamp.style.opacity = finePointer ? '1' : '0';

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const target = window.scrollY;
      if (reduced) {
        cur = target;
      } else {
        cur += (target - cur) * (1 - Math.exp(-7.5 * dt));
        if (Math.abs(target - cur) < 0.05) cur = target;
      }
      scroller.style.transform = `translate3d(0, ${-cur}px, 0)`;

      const heroH = heroArt ? heroArt.offsetHeight : 1;
      const hp = Math.min(1, Math.max(0, cur / heroH));
      if (heroArt && !reduced) heroArt.style.translate = `0 ${cur * 0.32}px`;
      if (heroCopy && !reduced) heroCopy.style.translate = `0 ${cur * 0.55}px`;
      if (title) title.style.setProperty('--lsx', `${(hp * 0.18).toFixed(4)}em`);

      if (lamp && finePointer && !reduced) {
        const k = 1 - Math.exp(-10 * dt);
        lx += (pointer.x - lx) * k;
        ly += (pointer.y - ly) * k;
        lamp.style.left = `${lx}px`;
        lamp.style.top = `${ly}px`;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', setBodyHeight);
      if (root) root.style.height = '';
    };
  }, [refs, themeKey]);
  /* eslint-enable react-hooks/immutability */
}

/** load intro: letters rise, subtitle opens, art un-zooms, nav slides down */
export function useIntro(refs: DescentRefs, themeKey: string): void {
  useEffect(() => {
    if (mm('(prefers-reduced-motion: reduce)')) return;
    if (typeof Element.prototype.animate !== 'function') return; // jsdom: no WAAPI
    const letters = refs.title.current?.querySelectorAll('.letter > span');
    letters?.forEach((el, i) => {
      el.animate([{ translateY: '110%' }, { translateY: '0%' }], {
        duration: 1200,
        delay: 250 + i * 70,
        easing: EASE,
        fill: 'forwards',
      });
    });
    const sub = document.querySelector('.hz-sub');
    sub?.animate(
      [
        { letterSpacing: '1.4em', transform: 'translateY(14px)', clipPath: 'inset(0 50% 0 50%)' },
        { letterSpacing: '0.62em', transform: 'translateY(0)', clipPath: 'inset(0)' },
      ],
      { duration: 1600, delay: 900, easing: EASE, fill: 'backwards' },
    );
    refs.heroArt.current?.animate([{ scale: '1.09' }, { scale: '1' }], {
      duration: 2600,
      easing: EASE,
      composite: 'add',
    });
    document.querySelector('.hz-nav')?.animate(
      [{ transform: 'translateY(-100%)' }, { transform: 'translateY(0)' }],
      { duration: 900, delay: 500, easing: EASE, fill: 'backwards' },
    );
  }, [refs, themeKey]);
}

/** copy blocks rise line by line the first time they pass 80 % of the viewport */
export function useReveals(scroller: RefObject<HTMLDivElement | null>, themeKey: string): void {
  useEffect(() => {
    const reduced = mm('(prefers-reduced-motion: reduce)');
    const blocks = scroller.current?.querySelectorAll<HTMLElement>('.hz-copy');
    if (!blocks) return;
    if (reduced || typeof IntersectionObserver === 'undefined' || typeof Element.prototype.animate !== 'function') {
      blocks.forEach((b) => b.classList.add('revealed'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const block = entry.target as HTMLElement;
          io.unobserve(block);
          block.querySelectorAll('.ln > span').forEach((line, i) => {
            line.animate([{ transform: 'translateY(105%)' }, { transform: 'translateY(0)' }], {
              duration: 1000,
              delay: i * 80,
              easing: EASE,
              fill: 'forwards',
            });
          });
          block.querySelector<HTMLElement>('.hz-rule')?.animate(
            [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
            { duration: 1100, delay: 160, easing: EASE, fill: 'forwards' },
          );
          block.classList.add('revealed');
        }
      },
      { rootMargin: '0px 0px -20% 0px' },
    );
    blocks.forEach((b) => io.observe(b));
    return () => io.disconnect();
  }, [scroller, themeKey]);
}

/**
 * Anchor navigation inside the fixed scroller: the browser cannot scroll to
 * layout boxes that live in a transformed fixed container, so #links glide
 * manually; the eased momentum loop does the actual animation.
 */
export function useAnchorScroll(scroller: RefObject<HTMLDivElement | null>): void {
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest('a[href^="#"]') as HTMLAnchorElement | null;
      const id = anchor?.getAttribute('href');
      if (!id || id === '#') return;
      const target = scroller.current?.querySelector(id);
      if (!target) return;
      e.preventDefault();
      window.scrollTo({ top: (target as HTMLElement).offsetTop });
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [scroller]);
}

/**
 * Scene-level sizing: on desktop the art box is 100vw; at ≤767px it widens
 * to keep the 16:9 painting undistorted and slides so the scene's focus x
 * lands at the screen centre. The seam bands follow the lower scene's
 * focus with the same formula.
 */
export function useResponsiveArt(rootRef: RefObject<HTMLElement | null>, themeKey: string): void {
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const layout = () => {
      const vw = window.innerWidth;
      const sceneH = vw * (1520 / 2688);
      const mobile = vw <= 767;
      const shownH = mobile ? Math.max(sceneH, window.innerHeight * 0.92) : sceneH;
      const artW = mobile ? Math.max(vw, (shownH * 2688) / 1520) : vw;
      el.style.setProperty('--artW', `${artW}px`);
      for (const node of el.querySelectorAll<HTMLElement>('[data-focus]')) {
        const focus = Number(node.dataset.focus);
        node.style.width = `${artW}px`;
        node.style.left = mobile ? `${vw / 2 - (focus / 100) * artW}px` : '0px';
      }
    };
    layout();
    window.addEventListener('resize', layout);
    return () => window.removeEventListener('resize', layout);
  }, [rootRef, themeKey]);
}
