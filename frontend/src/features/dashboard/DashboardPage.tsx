import { useCallback, useEffect, useState } from 'react'
import { env } from '../../shared/config/env'
import { ApiError, api } from '../../shared/api/client'
import type { DatabaseConfig, HealthResponse, Job, JobRequest, StatusResponse } from '../../shared/types'
import { DatabaseCard } from '../databases/DatabaseCard'
import { JobLogPanel } from '../jobs/JobLogPanel'
import { OperationPanel } from '../operations/OperationPanel'

export function DashboardPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [databases, setDatabases] = useState<DatabaseConfig[]>([])
  const [activeJob, setActiveJob] = useState<Job | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    try {
      const healthData = await api.health()
      setHealth(healthData)
      setConnected(true)
      const [statusData, dbData] = await Promise.all([
        api.getStatus(),
        api.getDatabases(),
      ])
      setStatus(statusData)
      setDatabases(dbData)
      setError(null)
    } catch (err) {
      setHealth(null)
      setConnected(false)
      setError(err instanceof Error ? err.message : 'Failed to connect to backend')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshStatus()
    const interval = setInterval(refreshStatus, env.statusRefreshMs)
    return () => clearInterval(interval)
  }, [refreshStatus])

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') {
      return
    }
    const poll = setInterval(async () => {
      try {
        const updated = await api.getJob(activeJob.id)
        setActiveJob(updated)
        if (updated.status === 'completed' || updated.status === 'failed') {
          refreshStatus()
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setActiveJob((current) =>
            current
              ? {
                  ...current,
                  status: 'failed',
                  error:
                    'Job was lost because the backend restarted (dev reload). Start the operation again.',
                }
              : null,
          )
          setError(
            'Job tracking was lost after a server reload. Re-run the operation to continue.',
          )
        }
      }
    }, env.jobPollMs)
    return () => clearInterval(poll)
  }, [activeJob, refreshStatus])

  const handleStartJob = async (request: JobRequest) => {
    setError(null)
    try {
      const job = await api.startJob(request)
      setActiveJob(job)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Another job is already running. Wait for it to finish before starting a new one.')
        return
      }
      setError(err instanceof Error ? err.message : 'Failed to start job')
    }
  }

  const handleResetTracking = async () => {
    if (!confirm('Reset restore cooldown tracking? All databases can be restored immediately.')) {
      return
    }
    try {
      await api.resetTracking()
      refreshStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset tracking')
    }
  }

  const jobRunning = activeJob?.status === 'pending' || activeJob?.status === 'running'

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>DB Restore Automation</h1>
          <p className="subtitle">PostgreSQL backup, restore, and validation</p>
        </div>
        <div className="header-actions">
          <span className={`connection-dot ${connected ? '' : 'offline'}`} />
          <span className="connection-label">
            {connected ? 'Backend connected' : 'Backend offline'}
            {health && (
              <span className="connection-meta">
                {' '}
                · {health.environment} · v{health.version}
                {health.auth_enabled ? ' · API key required' : ''}
              </span>
            )}
          </span>
          <button className="btn btn-ghost" onClick={refreshStatus} disabled={loading}>
            Refresh
          </button>
          <button className="btn btn-ghost" onClick={handleResetTracking} disabled={!connected}>
            Reset cooldown
          </button>
        </div>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && !status ? (
        <div className="loading">Loading status…</div>
      ) : (
        <>
          <section className="grid status-grid">
            {status?.backups.map((backup) => (
              <DatabaseCard
                key={backup.name}
                backup={backup}
                restore={status.restores.find((r) => r.source_name === backup.name)}
              />
            ))}
          </section>

          <div className="grid main-grid">
            <OperationPanel
              disabled={!connected || jobRunning}
              databases={databases}
              onStart={handleStartJob}
            />
            <JobLogPanel job={activeJob} />
          </div>
        </>
      )}
    </div>
  )
}
