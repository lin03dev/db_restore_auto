import { useEffect, useRef } from 'react'
import type { Job } from '../../shared/types'
import { StatusBadge } from '../../shared/components/StatusBadge'

function formatJobResult(result: Record<string, unknown> | null): string | null {
  if (!result) return null

  const lines: string[] = []
  if (result.partial) {
    lines.push('Partial success — some databases failed (often due to IP restrictions).')
  }
  if (typeof result.message === 'string') {
    lines.push(result.message)
  }

  const steps = result.steps as Record<string, { summary?: { failed?: string[]; succeeded?: string[] } }> | undefined
  if (steps) {
    for (const [stepName, step] of Object.entries(steps)) {
      const summary = step.summary
      if (!summary) continue
      if (summary.failed?.length) {
        lines.push(`${stepName} failed: ${summary.failed.join(', ')}`)
      }
      if (summary.succeeded?.length) {
        lines.push(`${stepName} succeeded: ${summary.succeeded.join(', ')}`)
      }
    }
  } else if (result.summary) {
    const summary = result.summary as { failed?: string[]; succeeded?: string[] }
    if (summary.failed?.length) lines.push(`Failed: ${summary.failed.join(', ')}`)
    if (summary.succeeded?.length) lines.push(`Succeeded: ${summary.succeeded.join(', ')}`)
  }

  return lines.length > 0 ? lines.join('\n') : null
}

interface Props {
  job: Job | null
}

export function JobLogPanel({ job }: Props) {
  const logRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [job?.logs])

  if (!job) {
    return (
      <div className="panel log-panel">
        <h2>Job Output</h2>
        <p className="empty-state">Start an operation to see live output here.</p>
      </div>
    )
  }

  const resultSummary = formatJobResult(job.result)

  return (
    <div className="panel log-panel">
      <div className="log-header">
        <div>
          <h2>Job Output</h2>
          <p className="mono job-id">Job {job.id} · {job.operation}</p>
        </div>
        <StatusBadge status={job.status} />
      </div>
      {job.error && <div className="error-banner">{job.error}</div>}
      {resultSummary && <div className="result-banner">{resultSummary}</div>}
      <pre ref={logRef} className="log-output">
        {job.logs.length > 0 ? job.logs.join('\n') : 'Waiting for output…'}
      </pre>
    </div>
  )
}
