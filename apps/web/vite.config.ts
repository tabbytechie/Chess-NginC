/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    // Dev parity with the prod nginx (apps/web/nginx.conf): same-origin /api
    // calls so the session-cookie auth flow works on the dev server too.
    // Without this, POST /api/v1/auth/login hits Vite's fallback (404) and
    // every login fails outside the Docker web container.
    proxy: {
      '/api': {
        // compose.yaml publishes the API as ${API_PORT:-8000}:8000; @types/node
        // is not a devDep here, so process.env access stays unwired — override
        // the target by editing this line if you run the API on a different port.
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // online-play WebSocket endpoint lives under /api/v1/online/ws
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Vitest does not restore spies by default; without this, mockResolvedValue
    // implementations leak between tests and real fetch calls get made.
    restoreMocks: true,
    // The review/board tests drive real python-chess analysis inside jsdom, and
    // under CI's parallel workers they run past the 5 s default purely from CPU
    // contention (observed 5.3–7.2 s) — never a logic failure. This headroom
    // makes the frontend gate deterministic instead of intermittently red.
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});
