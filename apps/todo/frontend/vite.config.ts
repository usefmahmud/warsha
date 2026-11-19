import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  // The SPA always calls `/api` on its own origin; in dev we proxy it to uvicorn.
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:PORT'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5174,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    preview: {
      port: 4174,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 900,
    },
  }
})
