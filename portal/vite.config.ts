import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/mission-control/',
  server: {
    port: 5190,
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
