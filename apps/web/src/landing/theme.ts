/**
 * Landing theme singleton. The descent's canvases paint fixed colour
 * constants (CSS variables cannot reach inside a draw call), so fields read
 * this flag when they build their palette; LandingPage flips it synchronously
 * in the toggle handler (NOT in an effect — child canvas effects run before
 * parent effects, so an effect-written value would be one flip stale) and
 * remounts the canvas subtree on a switch. Stored separately from the app
 * theme (chess-nginc-theme): the landing is a marketing surface and its
 * night/day choice should not drive the app UI.
 */
const KEY = 'hz-landing-theme';

function load(): boolean {
  try {
    return localStorage.getItem(KEY) === 'light';
  } catch {
    return false;
  }
}

// Hydrate at module import so a `light` choice persisted from a previous
// visit is already on themeState before the first canvas effect reads it.
export const themeState: { light: boolean } = { light: load() };

export function loadLandingTheme(): boolean {
  return themeState.light;
}

export function setLandingTheme(light: boolean): void {
  themeState.light = light;
  try {
    localStorage.setItem(KEY, light ? 'light' : 'dark');
  } catch {
    /* private mode: the in-memory flag still applies for this visit */
  }
}
