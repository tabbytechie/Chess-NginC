import { cleanup, configure } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';

// findBy*/waitFor default to a 1 s timeout. The review/board suites drive real
// python-chess analysis inside jsdom, and when the full run's parallel workers
// saturate the CPU those async queries spill past 1 s purely from scheduling
// (never a logic failure — each passes in isolation). Raising the ceiling once
// here makes the whole frontend gate deterministic instead of intermittently
// red on the slowest machine.
configure({ asyncUtilTimeout: 10000 });

// Vitest runs without `globals`, so RTL auto-cleanup never registers itself.
// Without this, rendered DOM leaks between tests and queries find duplicates.
afterEach(() => {
  cleanup();
});
