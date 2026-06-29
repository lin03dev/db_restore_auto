import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../shared/api/client'
import type {
  DatabaseConfig,
  DatabaseConnectivityResult,
  JobRequest,
  LocalPostgresStatus,
  OperationType,
} from '../../shared/types'

interface Props {
  disabled: boolean
  databases: DatabaseConfig[]
  onStart: (request: JobRequest) => void
}

type Preset = {
  label: string
  build: (base: JobRequest) => JobRequest
}

const PRESETS: Preset[] = [
  {
    label: 'Full Pipeline',
    build: (base) => ({ ...base, operation: 'pipeline' }),
  },
  {
    label: 'Backup Only',
    build: (base) => ({ ...base, operation: 'pipeline', skip_restore: true }),
  },
  {
    label: 'Restore Only',
    build: (base) => ({ ...base, operation: 'pipeline', skip_backup: true }),
  },
  {
    label: 'Validate Only',
    build: (base) => ({ ...base, operation: 'validate' }),
  },
  {
    label: 'Force All',
    build: (base) => ({
      ...base,
      operation: 'pipeline',
      force_backup: true,
      force_restore: true,
    }),
  },
]

function enabledNames(databases: DatabaseConfig[]) {
  return databases.filter((db) => db.enabled).map((db) => db.name)
}

export function OperationPanel({ disabled, databases, onStart }: Props) {
  const enabled = useMemo(() => databases.filter((db) => db.enabled), [databases])
  const [selected, setSelected] = useState<string[]>([])
  const [connectivity, setConnectivity] = useState<DatabaseConnectivityResult[] | null>(null)
  const [localPostgres, setLocalPostgres] = useState<LocalPostgresStatus | null>(null)
  const [testingConnections, setTestingConnections] = useState(false)
  const [testingLocal, setTestingLocal] = useState(false)
  const [connectivityError, setConnectivityError] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    setSelected(enabledNames(databases))
  }, [databases])

  const toggleDatabase = (name: string) => {
    setSelected((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    )
  }

  const selectAll = () => setSelected(enabled.map((db) => db.name))
  const clearSelection = () => setSelected([])

  const testConnections = async () => {
    if (selected.length === 0) {
      alert('Select at least one database to test remote connectivity.')
      return
    }
    setTestingConnections(true)
    setConnectivityError(null)
    try {
      const results = await api.checkConnectivity(selected)
      setConnectivity(results)
    } catch (err) {
      setConnectivity(null)
      setConnectivityError(err instanceof Error ? err.message : 'Connectivity check failed')
    } finally {
      setTestingConnections(false)
    }
  }

  const testLocalPostgres = async () => {
    setTestingLocal(true)
    setLocalError(null)
    try {
      const result = await api.checkLocalConnectivity()
      setLocalPostgres(result)
    } catch (err) {
      setLocalPostgres(null)
      setLocalError(err instanceof Error ? err.message : 'Local connectivity check failed')
    } finally {
      setTestingLocal(false)
    }
  }

  const baseRequest = (): JobRequest => ({ databases: selected })

  const runPreset = (preset: Preset) => {
    if (selected.length === 0) {
      alert('Select at least one database to dump, download, or restore.')
      return
    }
    onStart(preset.build(baseRequest()))
  }

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (selected.length === 0) {
      alert('Select at least one database to dump, download, or restore.')
      return
    }
    const form = new FormData(e.currentTarget)
    onStart({
      ...baseRequest(),
      operation: form.get('operation') as OperationType,
      force_backup: form.get('force_backup') === 'on',
      force_restore: form.get('force_restore') === 'on',
      skip_backup: form.get('skip_backup') === 'on',
      skip_restore: form.get('skip_restore') === 'on',
      skip_validation: form.get('skip_validation') === 'on',
      full_validation: form.get('full_validation') === 'on',
    })
  }

  return (
    <div className="panel">
      <h2>Operations</h2>
      <p className="panel-desc">
        Choose which databases to dump from remote (when your IP is allowed), then restore locally.
      </p>

      <section className="db-selector">
        <div className="db-selector-header">
          <h3>Databases to include</h3>
          <div className="db-selector-actions">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={testLocalPostgres}
              disabled={disabled || testingLocal}
            >
              {testingLocal ? 'Testing…' : 'Test local Postgres'}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={testConnections}
              disabled={disabled || testingConnections || selected.length === 0}
            >
              {testingConnections ? 'Testing…' : 'Test remote access'}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={selectAll} disabled={disabled}>
              Select all
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearSelection} disabled={disabled}>
              Clear
            </button>
          </div>
        </div>
        <p className="db-selector-hint">
          {selected.length === 0
            ? 'No databases selected — pick one or more below.'
            : `${selected.length} selected: ${selected.join(', ')}`}
        </p>
        <div className="db-checkbox-list">
          {enabled.map((db) => (
            <label key={db.name} className={`db-checkbox-item ${selected.includes(db.name) ? 'selected' : ''}`}>
              <input
                type="checkbox"
                checked={selected.includes(db.name)}
                onChange={() => toggleDatabase(db.name)}
                disabled={disabled}
              />
              <span className="db-checkbox-text">
                <strong>{db.name}</strong>
                <span className="mono">→ {db.target_db}</span>
                {db.description && <span className="db-checkbox-desc">{db.description}</span>}
              </span>
            </label>
          ))}
        </div>
        {localError && <p className="connectivity-error">{localError}</p>}
        {localPostgres && (
          <p className={`local-postgres-status ${localPostgres.reachable ? 'reachable' : 'unreachable'}`}>
            Local Postgres ({localPostgres.username}@{localPostgres.host}:{localPostgres.port}):{' '}
            {localPostgres.reachable
              ? 'reachable'
              : `${localPostgres.error_code || 'unreachable'}${localPostgres.message ? ` — ${localPostgres.message}` : ''}`}
          </p>
        )}
        {connectivityError && <p className="connectivity-error">{connectivityError}</p>}
        {connectivity && connectivity.length > 0 && (
          <ul className="connectivity-results">
            {connectivity.map((item) => (
              <li key={item.name} className={item.reachable ? 'reachable' : 'unreachable'}>
                <strong>{item.name}</strong>
                {item.reachable ? (
                  <span> — reachable from this machine</span>
                ) : (
                  <span>
                    {' '}
                    — {item.error_code || 'unreachable'}
                    {item.message ? `: ${item.message}` : ''}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="preset-grid">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            className="btn btn-secondary"
            disabled={disabled || selected.length === 0}
            onClick={() => runPreset(preset)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <AdvancedForm disabled={disabled} selectedCount={selected.length} onSubmit={handleSubmit} />
    </div>
  )
}

function AdvancedForm({
  disabled,
  selectedCount,
  onSubmit,
}: {
  disabled: boolean
  selectedCount: number
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void
}) {
  return (
    <details className="advanced-form">
      <summary>Advanced options</summary>
      <form onSubmit={onSubmit}>
        <div className="form-row">
          <label>
            Operation
            <select name="operation" defaultValue="pipeline">
              <option value="pipeline">Full pipeline</option>
              <option value="backup">Backup only</option>
              <option value="restore">Restore only</option>
              <option value="validate">Validate only</option>
            </select>
          </label>
        </div>
        <div className="checkbox-grid">
          <label><input type="checkbox" name="force_backup" /> Force backup</label>
          <label><input type="checkbox" name="force_restore" /> Force restore</label>
          <label><input type="checkbox" name="skip_backup" /> Skip backup</label>
          <label><input type="checkbox" name="skip_restore" /> Skip restore</label>
          <label><input type="checkbox" name="skip_validation" /> Skip validation</label>
          <label><input type="checkbox" name="full_validation" /> Full validation</label>
        </div>
        <button type="submit" className="btn btn-primary" disabled={disabled || selectedCount === 0}>
          Run custom job
        </button>
      </form>
    </details>
  )
}
