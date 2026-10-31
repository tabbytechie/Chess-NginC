/**
 * React wrappers around the canvas engine. Each canvas registers with the
 * shared ticker and only draws while within ~50px of the viewport. Sizing
 * runs on window resize (the descent is a single tall page, so one global
 * resize listener is plenty).
 */
import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

import { DustField, FallField, registerField } from './effects';
import type { DustSpec, FallBox } from './data';

/** viewport gating fires resize()/frame() callbacks; specs are module-constant so identity is stable */
function useField(
  ref: RefObject<HTMLCanvasElement | null>,
  build: () => FallField | DustField,
  deps: unknown[],
): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const field = build();
    field.active = false;

    let io: IntersectionObserver | null = null;
    if (typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver(
        ([entry]) => {
          field.active = entry.isIntersecting;
        },
        { rootMargin: '50px 0px' },
      );
      io.observe(el);
    } else {
      field.active = true;
    }

    const onResize = () => field.resize();
    window.addEventListener('resize', onResize);
    const unregister = registerField(field);
    onResize();

    return () => {
      unregister();
      io?.disconnect();
      window.removeEventListener('resize', onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- specs are module constants
  }, [ref, build, ...deps]);
}

export function FallCanvas({
  spec,
  body,
  style,
  className,
}: {
  spec: FallBox;
  /** seam streams fill a water body behind the painted band */
  body?: boolean;
  style?: React.CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useField(ref, () => new FallField(ref.current!, spec.kind, spec.speed, body), [spec, body]);

  const pos: React.CSSProperties = {
    left: `${spec.l}%`,
    top: `${spec.t}%`,
    width: `${spec.w}%`,
    height: `${spec.h}%`,
    ...style,
  };
  return <canvas ref={ref} className={`hz-fall${className ? ` ${className}` : ''}`} style={pos} aria-hidden="true" />;
}

export function DustCanvas({ spec }: { spec: DustSpec }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useField(ref, () => new DustField(ref.current!, spec.kind, spec.count, spec.box), [spec]);
  // no inline mixBlendMode: landing.css owns .hz-dust's blend so it can flip
  // to `normal` in day mode (inline styles would override the theme token).
  return <canvas ref={ref} className="hz-dust" aria-hidden="true" />;
}
