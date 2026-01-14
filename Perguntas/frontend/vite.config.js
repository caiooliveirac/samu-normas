import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    hmr: {
      host: process.env.VITE_HMR_HOST || undefined,
      clientPort: process.env.VITE_HMR_CLIENT_PORT ? Number(process.env.VITE_HMR_CLIENT_PORT) : undefined,
    },
    proxy: {
      '/api': {
        // Quando o Vite roda no host, 127.0.0.1:8000 funciona.
        // Quando roda em container, use: VITE_PROXY_TARGET=http://web:8000
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(__dirname, '../static/react'),
    assetsDir: 'assets',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: resolve(__dirname, 'src/main.jsx'),
    },
  },
  base: '/static/react/',
})
