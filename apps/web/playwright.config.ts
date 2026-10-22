import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end config for the composed stack (Phase 5). These specs drive a real
 * browser against a running `docker compose` deployment — the only job that
 * proves API + engine + web work together. Run with `npx playwright test`.
 *
 * The base URL is the published web edge (nginx on WEB_PORT). Point it at a
 * deployment with `E2E_BASE_URL`; CI does exactly that.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

export default defineConfig({
  testDir: './e2e',
  // Single worker: every spec mutates shared state on one composed stack
  // (accounts, rate-limit buckets), so they must not run concurrently.
  fullyParallel: false,
  workers: 1,
  // CI tolerates transient container/latency flakes; locally a failure is real.
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    // One mobile-viewport pass of the same play loop.
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
});
