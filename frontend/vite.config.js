import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// /api is proxied to the FastAPI backend in development (production: nginx does the same, see nginx.conf)
const API = process.env.VITE_PROXY_API || 'http://127.0.0.1:8000'
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: '0.0.0.0', port: 5175, strictPort: true, proxy: { '/api': { target: API, changeOrigin: false } } },
  preview: { host: '0.0.0.0', port: 5175, proxy: { '/api': { target: API } } },
  build: { chunkSizeWarningLimit: 1500 },
})
