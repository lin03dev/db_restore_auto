/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_KEY?: string
  readonly VITE_BACKEND_PORT?: string
  readonly VITE_DEV_PORT?: string
  readonly VITE_STATUS_REFRESH_MS?: string
  readonly VITE_JOB_POLL_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
