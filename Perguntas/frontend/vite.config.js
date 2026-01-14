import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig(({ command }) => {
  const isBuild = command === 'build'

  // Para compartilhar o link do hostname (ex.: DNS da EC2) sem usar IP direto.
  // O Vite bloqueia hosts desconhecidos por segurança (DNS rebinding).
  const allowedHosts = [
    'ec2-3-150-194-173.us-east-2.compute.amazonaws.com',
  ]

  return {
    plugins: [react()],
    // Dev: React independente (base '/'). Build: compatível com Django (base '/static/react/').
    base: process.env.VITE_BASE || (isBuild ? '/static/react/' : '/'),
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      allowedHosts,
      hmr: {
        host: process.env.VITE_HMR_HOST || undefined,
        clientPort: process.env.VITE_HMR_CLIENT_PORT ? Number(process.env.VITE_HMR_CLIENT_PORT) : undefined,
      },
      proxy: {
        '/api': {
          // Dev integrado: VITE_PROXY_TARGET=http://backend:8000 (compose)
          // Dev local: VITE_PROXY_TARGET=http://127.0.0.1:8000
          target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      // Mantém o build compatível com o fluxo atual (Django servindo /static/react).
      outDir: isBuild ? resolve(__dirname, '../static/react') : resolve(__dirname, 'dist'),
      assetsDir: 'assets',
      emptyOutDir: true,
      manifest: true,
      rollupOptions: {
        input: resolve(__dirname, 'src/main.jsx'),
      },
    },
  }
})
