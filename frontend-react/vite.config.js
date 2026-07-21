import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = 'http://127.0.0.1:8000'

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
      '/auth': backendTarget,
      '/threads': backendTarget,
      '/chat': backendTarget,
      '/rag': backendTarget,
      '/admin': backendTarget,
      '/mcp': backendTarget,
      '/workspaces': backendTarget,
      '/sources': backendTarget,
      '/search': backendTarget,
      '/public': backendTarget,
    }
  }
})
