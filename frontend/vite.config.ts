import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 43123,
    proxy: {
      '/api': {
        // Local: 127.0.0.1; docker-compose: set VITE_DEV_API_PROXY=http://backend:8801
        target: process.env.VITE_DEV_API_PROXY ?? 'http://127.0.0.1:8801',
        changeOrigin: true,
      },
    },
  },
})