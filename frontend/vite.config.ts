import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/auth": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/chat": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/agent": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/jd": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/jobs": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
})
