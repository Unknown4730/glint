/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Base URL of the FastAPI backend.
   *
   * Leave this empty (the default) to use relative "/api" URLs, which the Vite
   * dev server proxies to http://127.0.0.1:8000. Set it explicitly only when
   * the frontend is served from somewhere else, e.g.
   * VITE_API_BASE_URL=http://127.0.0.1:8000
   */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
