import { env } from '../config/env'
import type {
  DatabaseConfig,
  DatabaseConnectivityResult,
  HealthResponse,
  Job,
  JobRequest,
  LocalPostgresStatus,
  StatusResponse,
} from '../types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(extra as Record<string, string>),
  }
  if (env.apiKey) {
    headers['X-API-Key'] = env.apiKey
  }
  return headers
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${env.apiBase}${path}`, {
    ...options,
    headers: buildHeaders(options?.headers),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = body.detail
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).join(', ')
      : detail
    throw new ApiError(message || `Request failed (${res.status})`, res.status)
  }

  return res.json()
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  getStatus: () => request<StatusResponse>('/status'),
  getDatabases: () => request<DatabaseConfig[]>('/databases'),
  checkConnectivity: (databases: string[]) =>
    request<DatabaseConnectivityResult[]>('/databases/connectivity', {
      method: 'POST',
      body: JSON.stringify({ databases }),
    }),
  checkLocalConnectivity: () =>
    request<LocalPostgresStatus>('/databases/local-connectivity'),
  resetTracking: () =>
    request<{ success: boolean; message: string }>('/reset-tracking', {
      method: 'POST',
    }),
  startJob: (body: JobRequest) =>
    request<Job>('/jobs', { method: 'POST', body: JSON.stringify(body) }),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  listJobs: (limit = 20) => request<Job[]>(`/jobs?limit=${limit}`),
}
