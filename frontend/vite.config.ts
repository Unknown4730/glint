import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Read a GLINT_* setting from the real process environment first and from the
 * .env files second. Shell variables always win, which keeps start.ps1 simple.
 */
function glintEnv(
  key: string,
  fallback: string,
  fileEnv: Record<string, string>,
): string {
  const fromProcess = process.env[key]
  if (fromProcess && fromProcess.trim() !== '') return fromProcess.trim()
  const fromFile = fileEnv[key]
  if (fromFile && fromFile.trim() !== '') return fromFile.trim()
  return fallback
}

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), 'GLINT_')

  const backendUrl = glintEnv('GLINT_BACKEND_URL', 'http://127.0.0.1:8000', fileEnv)
  const host = glintEnv('GLINT_FRONTEND_HOST', '127.0.0.1', fileEnv)
  const port = Number(glintEnv('GLINT_FRONTEND_PORT', '5173', fileEnv))
  const rawAllowedHosts = glintEnv('GLINT_FRONTEND_ALLOWED_HOSTS', '', fileEnv)

  // By default Vite only answers requests for localhost. Set
  // GLINT_FRONTEND_ALLOWED_HOSTS="*" (or a comma separated list) if the dev
  // server must answer under another host name, e.g. inside a tunnel.
  const allowedHosts: true | string[] =
    rawAllowedHosts === ''
      ? ['localhost', '127.0.0.1']
      : rawAllowedHosts === '*' || rawAllowedHosts === 'true'
        ? true
        : rawAllowedHosts
            .split(',')
            .map((entry) => entry.trim())
            .filter(Boolean)

  // The browser only ever talks to the Vite origin; "/api" is forwarded to the
  // FastAPI server. This removes CORS problems in development entirely.
  const proxy = {
    '/api': {
      target: backendUrl,
      changeOrigin: true,
    },
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host,
      port,
      strictPort: false,
      allowedHosts,
      proxy,
    },
    preview: {
      host,
      port,
      allowedHosts,
      proxy,
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      sourcemap: false,
      target: 'es2022',
      chunkSizeWarningLimit: 1000,
    },
  }
})
