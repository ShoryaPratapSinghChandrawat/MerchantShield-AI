import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
// Single source of truth for hosts and ports, shared with the Playwright run
// so the two can never drift apart.
import { DEV_PORT, E2E_HOST } from './tests/paths.ts';

/**
 * Dev: Vite serves the SPA on 127.0.0.1:5174 and proxies /api to the FastAPI
 *      backend.
 * Prod: `vite build` emits ./dist, which FastAPI serves itself with SPA
 *       fallback. One deployable service (section 5).
 *
 * No wildcard CORS is needed in either mode, because the browser always talks
 * to a single origin.
 *
 * `host` is pinned to the literal 127.0.0.1 rather than `localhost`: it keeps
 * the dev server off the local network, and it avoids the Windows case where
 * `localhost` resolves to ::1 while the server listens on IPv4.
 * `strictPort` makes a busy port a loud failure instead of a silent move to
 * the next free port, which would leave the proxy pointing nowhere.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: E2E_HOST,
    port: DEV_PORT,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env['MS_BACKEND_URL'] ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
});
