import type { BackupInfo, RestoreInfo } from '../../shared/types'
import { StatusBadge } from '../../shared/components/StatusBadge'

function formatSize(mb: number) {
  if (mb < 1) return `${(mb * 1024).toFixed(1)} KB`
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  return `${(mb / 1024).toFixed(2)} GB`
}

interface Props {
  backup: BackupInfo
  restore: RestoreInfo | undefined
}

export function DatabaseCard({ backup, restore }: Props) {
  return (
    <div className="card">
      <div className="card-header">
        <h3>{backup.name}</h3>
        <StatusBadge status={backup.status} />
      </div>

      <div className="card-section">
        <h4>Backup</h4>
        <dl>
          <div>
            <dt>Dump file</dt>
            <dd className="mono">{backup.dump_file.split('/').pop()}</dd>
          </div>
          <div>
            <dt>Size</dt>
            <dd>{backup.exists ? formatSize(backup.size_mb) : '—'}</dd>
          </div>
          <div>
            <dt>Age</dt>
            <dd>
              {backup.age_days != null ? `${backup.age_days} days` : '—'}
              {backup.needs_refresh && backup.exists && (
                <span className="hint-warning"> · refresh recommended</span>
              )}
            </dd>
          </div>
        </dl>
      </div>

      {restore && (
        <div className="card-section">
          <h4>Restore → {restore.target_db}</h4>
          <dl>
            <div>
              <dt>Status</dt>
              <dd><StatusBadge status={restore.status} /></dd>
            </div>
            <div>
              <dt>Last restore</dt>
              <dd>
                {restore.last_restore
                  ? new Date(restore.last_restore).toLocaleDateString()
                  : 'Never'}
              </dd>
            </div>
            {restore.days_ago != null && (
              <div>
                <dt>Days ago</dt>
                <dd>{restore.days_ago}</dd>
              </div>
            )}
            <div>
              <dt>Can restore</dt>
              <dd>{restore.can_restore ? 'Yes' : 'No (cooldown)'}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
