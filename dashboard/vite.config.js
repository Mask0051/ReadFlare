import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config.
// The proxy forwards any request starting with /api to the Python API
// (api.py, default port 5000). This means the React code can always call
// relative URLs like "/api/status" and we avoid CORS problems in development.
// Docs: https://vite.dev/config/server-options.html#server-proxy
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
