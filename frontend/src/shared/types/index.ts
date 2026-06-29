export type OperationType = 'pipeline' | 'backup' | 'restore' | 'validate'
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface BackupInfo {
  name: string
  dump_file: string
  exists: boolean
  size_mb: number
  age_days: number | null
  needs_refresh: boolean
  status: string
}

export interface RestoreInfo {
  target_db: string
  source_name: string
  last_restore: string | null
  days_ago: number | null
  can_restore: boolean
  status: string
}

export interface StatusResponse {
  backups: BackupInfo[]
  restores: RestoreInfo[]
}

export interface DatabaseConfig {
  name: string
  target_db: string
  source_dump: string
  enabled: boolean
  description?: string | null
}

export interface DatabaseConnectivityResult {
  name: string
  reachable: boolean
  error_code?: string | null
  message?: string | null
}

export interface LocalPostgresStatus {
  reachable: boolean
  host: string
  port: string
  username: string
  error_code?: string | null
  message?: string | null
}

export interface JobRequest {
  operation?: OperationType
  databases?: string[]
  database?: string
  force_backup?: boolean
  force_restore?: boolean
  skip_backup?: boolean
  skip_restore?: boolean
  skip_validation?: boolean
  full_validation?: boolean
}

export interface Job {
  id: string
  operation: OperationType
  status: JobStatus
  databases: string[]
  database: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  logs: string[]
  result: Record<string, unknown> | null
  error: string | null
}

export interface HealthResponse {
  status: string
  environment: string
  auth_enabled: boolean
  version: string
}
