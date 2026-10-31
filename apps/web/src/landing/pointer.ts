/**
 * Cursor singleton for the descent: one passive pointermove listener feeds
 * the ghost repulsion loop and the lantern glow. Kept in its own module so
 * component files only export components (fast-refresh rule).
 */
export const pointer = { x: -9999, y: -9999 };

if (typeof window !== 'undefined') {
  window.addEventListener(
    'pointermove',
    (e) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
    },
    { passive: true },
  );
}
