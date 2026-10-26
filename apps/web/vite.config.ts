/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
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
