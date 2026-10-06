import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The Flask API the dev server forwards /api to (used with VITE_API_BASE_URL=/).
const API_TARGET = process.env.NIVARA_API_TARGET ?? 'http://localhost:5001'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin API: the browser talks only to this server, so session
    // cookies stay first-party (needed in GitHub Codespaces, where each port
    // gets its own *.app.github.dev address).
    proxy: { '/api': { target: API_TARGET, changeOrigin: false } },
    allowedHosts: ['localhost', '.app.github.dev'],
  },
})
