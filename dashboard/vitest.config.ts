import path from 'path';
import { defineConfig } from 'vitest/config';

/**
 * vitest.config.ts — frontend runtime test setup.
 *
 * The dashboard previously had NO frontend test runner: `npm run build`
 * (compile + type-check) passed even while the Boosters page crashed in
 * production with minified React error #310 (a Rules-of-Hooks violation
 * that only manifests across the loading → loaded render transition).
 * These tests render real components in jsdom so hook-order regressions
 * fail in CI instead of in production.
 *
 * esbuild jsx is forced to 'automatic' because tsconfig sets
 * "jsx": "preserve" (Next.js requirement), which vite/esbuild would
 * otherwise pass through untransformed.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname),
    },
  },
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{ts,tsx}'],
    globals: false,
  },
});
