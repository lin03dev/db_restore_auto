const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

export const env = {
  apiBase: API_BASE,
  apiKey: API_KEY,
  statusRefreshMs: Number(import.meta.env.VITE_STATUS_REFRESH_MS ?? 15000),
  jobPollMs: Number(import.meta.env.VITE_JOB_POLL_MS ?? 1500),
}
