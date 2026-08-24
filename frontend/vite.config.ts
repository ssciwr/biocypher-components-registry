import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  const backendTarget = env.BACKEND_BASE_URL || env.VITE_API_BASE_URL || 'http://localhost:8000'

  return {
    envDir: '..',
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/agent/api': { changeOrigin: true, target: backendTarget },// looks weird, but /agent/api will be preserved.
        '/api': { changeOrigin: true, target: backendTarget },
      },
    },
  }
})
