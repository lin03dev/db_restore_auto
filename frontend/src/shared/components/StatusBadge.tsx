import type { JobStatus } from '../types'

const STATUS_CONFIG: Record<JobStatus | string, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'badge badge-muted' },
  running: { label: 'Running', className: 'badge badge-info' },
  completed: { label: 'Completed', className: 'badge badge-success' },
  failed: { label: 'Failed', className: 'badge badge-danger' },
  fresh: { label: 'Fresh', className: 'badge badge-success' },
  stale: { label: 'Stale', className: 'badge badge-warning' },
  missing: { label: 'Missing', className: 'badge badge-danger' },
  never: { label: 'Never restored', className: 'badge badge-muted' },
  ready: { label: 'Ready', className: 'badge badge-success' },
  cooldown: { label: 'Cooldown', className: 'badge badge-warning' },
}

interface Props {
  status: string
}

export function StatusBadge({ status }: Props) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: 'badge badge-muted' }
  return <span className={config.className}>{config.label}</span>
}
