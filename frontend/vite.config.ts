import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// db_restore_auto ports (avoid conflicts with rx_pm on 8000/5173)
const BACKEND_PORT = process.env.VITE_BACKEND_PORT ?? '8002'
const FRONTEND_PORT = Number(process.env.VITE_DEV_PORT ?? 5174)

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },
})
