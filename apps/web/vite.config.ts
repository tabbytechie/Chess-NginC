/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy the API so the browser talks to a single origin. This keeps the
    // session cookie first-party (SameSite=Lax) instead of cross-origin, and
    // means the dev server needs no VITE_API_BASE override.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Vitest does not restore spies by default; without this, mockResolvedValue
    // implementations leak between tests and real fetch calls get made.
    restoreMocks: true,
    // The e2e/ specs are Playwright tests (run by `playwright test`), not Vitest
    // units; without this the `*.spec.ts` default glob would try to run them.
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
  },
});
