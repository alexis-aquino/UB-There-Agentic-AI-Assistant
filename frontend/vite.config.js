import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Override with BACKEND_URL to point the dev server at a backend on another port.
const BACKEND = process.env.BACKEND_URL || 'http://localhost:8100';

export default defineConfig({
  plugins: [react()],
  server: {
    // 5273 is the port the docs and the backend's CORS list expect. strictPort: fail
    // loudly if it is taken instead of silently moving somewhere else.
    port: 5273,
    strictPort: true,
    proxy: {
      // The app's API calls go through this server to the backend, so a phone only needs
      // to reach port 5273 and the backend stays on this PC. Voice recording endpoints are
      // deliberately not forwarded: they are backend-only.
      '^/api/(?!voice/(dataset|sample))': { target: BACKEND, xfwd: true },
      // The page office staff open from the "answer here" email link.
      '^/answer/': { target: BACKEND, xfwd: true },
    },
  },
});
