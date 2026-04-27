import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.[jt]sx?$/,
    exclude: [],
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: { '.js': 'jsx' },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth':    'http://localhost:8000',
      '/threads': 'http://localhost:8000',
      '/chat':    'http://localhost:8000',
      '/rag':     'http://localhost:8000',
      '/admin':   'http://localhost:8000',
    }
  }
})
