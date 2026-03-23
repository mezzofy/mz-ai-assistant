import React, { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Activity, RefreshCw, ChevronDown, ChevronRight, Copy, Check, Play, Pause, RotateCcw, X, Download, GitBranch, AlertCircle, CheckCircle, Clock, ArrowRight } from 'lucide-react'
import { portalApi, getPlans, getPlanDetail } from '../api/portal'
import { AgentTask, ScheduledJob, TaskStats, Plan, PlanDetail, PlanStep } from '../types'

// ── Status helpers ─────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  queued: '#6B7280',
  running: '#f97316',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#6B7280',
  revoked: '#6B7280',
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'PENDING',
  running: 'RUNNING',
  completed: 'COMPLETED',
  failed: 'FAILED',
  cancelled: 'CANCELLED',
  revoked: 'CANCELLED',
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status === 'revoked' ? 'cancelled' : status
  const color = STATUS_COLORS[normalized] ?? '#6B7280'
  const label = STATUS_LABELS[status] ?? status.toUpperCase()
  const isPulse = normalized === 'running'

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full`}
      style={{ background: `${color}22`, color }}
    >
      {isPulse && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: color }} />
          <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: color }} />
        </span>
      )}
      {label}
    </span>
  )
}

// ── Plan status badge ────────────────────────────────────────────────────────

function PlanStatusBadge({ status }: { status: Plan['status'] }) {
  if (status === 'IN_PROGRESS') {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full"
        style={{ background: '#f9731622', color: '#f97316' }}
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: '#f97316' }} />
          <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#f97316' }} />
        </span>
        IN PROGRESS
      </span>
    )
  }
  if (status === 'COMPLETED') {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full"
        style={{ background: '#00000044', color: '#ffffff', border: '1px solid #333' }}
      >
        ✓ COMPLETED
      </span>
    )
  }
  if (status === 'FAILED') {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full"
        style={{ background: '#ef444422', color: '#ef4444' }}
      >
        ✗ FAILED
      </span>
    )
  }
  // PENDING
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full"
      style={{ background: '#6B728022', color: '#6B7280' }}
    >
      PENDING
    </span>
  )
}

// ── Progress bar ────────────────────────────────────────────────────────────

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full rounded-full h-1.5" style={{ background: '#1E293B' }}>
      <div
        className="h-1.5 rounded-full transition-all"
        style={{ width: `${value}%`, background: '#f97316' }}
      />
    </div>
  )
}

// ── Copy button ─────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button onClick={copy} className="text-gray-400 hover:text-white transition-colors ml-1" title="Copy">
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  )
}

// ── Stat pill ───────────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border"
      style={{ borderColor: color ? `${color}44` : '#1E3A5F', color: color ?? '#94A3B8' }}
    >
      <span className="font-bold" style={{ color: color ?? 'white' }}>{value}</span>
      {label}
    </span>
  )
}

// ── Task card ───────────────────────────────────────────────────────────────

function TaskCard({ task, onKill, onDelete }: {
  task: AgentTask
  onKill: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  const canKill = task.status === 'queued' || task.status === 'running'
  const canDownload = task.status === 'completed' && !!(task.details &&
    (
      (task.details as Record<string, unknown>).file_path ||
      (task.details as Record<string, unknown>).output_path
    ))

  const timeAgo = (iso: string | null) => {
    if (!iso) return ''
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
  }

  const normalized = task.status === 'revoked' ? 'cancelled' : task.status

  return (
    <div
      className="rounded-lg border p-4 transition-all"
      style={{
        background: '#0f172a',
        borderColor: normalized === 'running' ? '#f9731644' : '#1E3A5F',
      }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <StatusBadge status={task.status} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white truncate">{task.content || '(no message)'}</p>
            <p className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
              {task.department && <span className="capitalize">{task.department}</span>}
              {task.triggered_by_name && <span> · {task.triggered_by_name}</span>}
              {task.created_at && <span> · {timeAgo(task.created_at)}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {canDownload && (
            <button
              onClick={() => {
                const path = (task.details as Record<string, unknown>).file_path ||
                  (task.details as Record<string, unknown>).output_path
                if (path) window.open(`/files/${path}/download`, '_blank')
              }}
              className="text-xs px-2 py-1 rounded border transition-colors"
              style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
              title="Download result"
            >
              <Download size={12} />
            </button>
          )}
          {canKill && (
            <button
              onClick={() => {
                if (window.confirm('Kill this task?')) onKill(task.id)
              }}
              className="text-xs px-2 py-1 rounded border transition-colors hover:border-red-500/50 hover:text-red-400"
              style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
              title="Kill task"
            >
              <X size={12} />
            </button>
          )}
          {normalized === 'completed' || normalized === 'failed' || normalized === 'cancelled' ? (
            <button
              onClick={() => {
                if (window.confirm('Delete this task from history?')) onDelete(task.id)
              }}
              className="text-xs px-2 py-1 rounded border transition-colors hover:border-red-500/50 hover:text-red-400"
              style={{ borderColor: '#1E3A5F', color: '#6B7280' }}
              title="Delete from history"
            >
              Delete
            </button>
          ) : null}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        </div>
      </div>

      {/* Progress bar (running only) */}
      {normalized === 'running' && task.progress != null && (
        <div className="mt-3">
          <div className="flex justify-between text-xs mb-1" style={{ color: '#6B7280' }}>
            <span>{task.current_step || 'Processing...'}</span>
            <span>{task.progress}%</span>
          </div>
          <ProgressBar value={task.progress} />
        </div>
      )}

      {/* Error */}
      {normalized === 'failed' && task.error && (
        <p className="mt-2 text-xs font-mono" style={{ color: '#ef4444' }}>
          {task.error}
        </p>
      )}

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-3 pt-3 border-t space-y-2" style={{ borderColor: '#1E3A5F' }}>
          <div className="flex items-center gap-1 text-xs" style={{ color: '#6B7280' }}>
            <span>ID:</span>
            <span className="font-mono text-gray-300">{task.id}</span>
            <CopyButton text={task.id} />
          </div>
          {task.task_ref && (
            <div className="flex items-center gap-1 text-xs" style={{ color: '#6B7280' }}>
              <span>Celery ref:</span>
              <span className="font-mono text-gray-300">{task.task_ref}</span>
              <CopyButton text={task.task_ref} />
            </div>
          )}
          {task.details && (
            <div className="space-y-2 text-xs">
              {typeof (task.details as Record<string, unknown>).response === 'string' && (
                <div>
                  <div className="mb-1" style={{ color: '#6B7280' }}>Response</div>
                  <div
                    className="p-2 rounded"
                    style={{
                      background: '#1E293B',
                      color: '#E2E8F0',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      maxHeight: '300px',
                      overflowY: 'auto',
                    }}
                  >
                    {(task.details as Record<string, unknown>).response as string}
                  </div>
                </div>
              )}
              <details>
                <summary className="cursor-pointer" style={{ color: '#94A3B8' }}>Raw JSON</summary>
                <pre className="mt-1 p-2 rounded overflow-x-auto font-mono" style={{ background: '#1E293B', color: '#94A3B8', maxHeight: '200px', overflowY: 'auto' }}>
                  {JSON.stringify(task.details, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Scheduled job row ───────────────────────────────────────────────────────

function ScheduledJobRow({ job, onRun, onPause, onResume }: {
  job: ScheduledJob
  onRun: (id: string) => void
  onPause: (id: string) => void
  onResume: (id: string) => void
}) {
  const formatDate = (iso: string | null) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleString()
  }

  return (
    <tr className="border-b" style={{ borderColor: '#1E3A5F' }}>
      <td className="px-4 py-3">
        <div className="text-sm text-white">{job.name}</div>
        {job.user_name && (
          <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>{job.user_name}</div>
        )}
      </td>
      <td className="px-4 py-3 text-sm capitalize" style={{ color: '#94A3B8' }}>{job.agent}</td>
      <td className="px-4 py-3 text-xs font-mono" style={{ color: '#94A3B8' }}>{job.schedule}</td>
      <td className="px-4 py-3 text-xs" style={{ color: '#94A3B8' }}>{formatDate(job.next_run)}</td>
      <td className="px-4 py-3 text-xs" style={{ color: '#94A3B8' }}>{formatDate(job.last_run)}</td>
      <td className="px-4 py-3">
        <span className="flex items-center gap-1.5 text-xs">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: job.is_active ? '#22c55e' : '#6B7280' }}
          />
          <span style={{ color: job.is_active ? '#22c55e' : '#6B7280' }}>
            {job.is_active ? 'Active' : 'Paused'}
          </span>
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onRun(job.id)}
            className="text-xs px-2 py-1 rounded border transition-colors hover:border-orange-500/50"
            style={{ borderColor: '#1E3A5F', color: '#f97316' }}
            title="Run now"
          >
            <Play size={11} />
          </button>
          {job.is_active ? (
            <button
              onClick={() => onPause(job.id)}
              className="text-xs px-2 py-1 rounded border transition-colors hover:border-yellow-500/50 hover:text-yellow-400"
              style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
              title="Pause"
            >
              <Pause size={11} />
            </button>
          ) : (
            <button
              onClick={() => onResume(job.id)}
              className="text-xs px-2 py-1 rounded border transition-colors hover:border-green-500/50 hover:text-green-400"
              style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
              title="Resume"
            >
              <RotateCcw size={11} />
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

// ── Plan helpers ─────────────────────────────────────────────────────────────

function formatDuration(ms?: number): string {
  if (!ms) return ''
  const totalSec = Math.floor(ms / 1000)
  const mins = Math.floor(totalSec / 60)
  const secs = totalSec % 60
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

function formatDurationFromDates(start: string, end?: string): string {
  if (!end) return ''
  const ms = new Date(end).getTime() - new Date(start).getTime()
  return formatDuration(ms)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function stripAgentPrefix(agentId: string): string {
  return agentId.replace(/^agent_/, '')
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function qualityDot(score: number): React.ReactNode {
  const color = score >= 0.8 ? '#22c55e' : score >= 0.6 ? '#f97316' : '#ef4444'
  return (
    <span
      className="inline-block w-2 h-2 rounded-full ml-1 shrink-0"
      style={{ background: color }}
      title={`Quality: ${Math.round(score * 100)}%`}
    />
  )
}

// ── Step status icon ──────────────────────────────────────────────────────────

function StepIcon({ status }: { status: string }) {
  const s = status.toLowerCase()
  if (s === 'completed') {
    return <CheckCircle size={16} style={{ color: '#22c55e' }} />
  }
  if (s === 'started' || s === 'in_progress') {
    return <ArrowRight size={16} style={{ color: '#f97316' }} />
  }
  if (s === 'retrying') {
    return <RotateCcw size={16} style={{ color: '#f97316' }} />
  }
  if (s === 'failed') {
    return <AlertCircle size={16} style={{ color: '#ef4444' }} />
  }
  // pending
  return <Clock size={16} style={{ color: '#6B7280' }} />
}

// ── Expandable section ────────────────────────────────────────────────────────

function ExpandSection({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs px-2 py-0.5 rounded border transition-colors mt-1"
        style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        {label}
      </button>
      {open && (
        <div
          className="mt-1 p-2 rounded text-xs"
          style={{ background: '#1E293B', color: '#E2E8F0' }}
        >
          {children}
        </div>
      )}
    </div>
  )
}

// ── Plan step row ─────────────────────────────────────────────────────────────

function PlanStepRow({ step }: { step: PlanStep }) {
  const agentLabel = capitalizeFirst(stripAgentPrefix(step.agent_id))
  const statusLower = step.status.toLowerCase()
  const isCompleted = statusLower === 'completed'
  const isActive = statusLower === 'started' || statusLower === 'in_progress' || statusLower === 'retrying'
  const isFailed = statusLower === 'failed'

  const review = step.review as Record<string, unknown> | undefined

  return (
    <div
      className="flex gap-3 py-3 border-b last:border-b-0"
      style={{ borderColor: '#1E3A5F' }}
    >
      {/* Icon column */}
      <div className="flex flex-col items-center pt-0.5 shrink-0">
        <StepIcon status={step.status} />
        <div className="w-px flex-1 mt-1" style={{ background: '#1E3A5F', minHeight: '8px' }} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-1">
        <div className="flex items-center flex-wrap gap-2">
          <span className="text-xs font-semibold text-white">
            Step {step.step_number} · {agentLabel}
          </span>
          {step.retry_count > 0 && (
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: '#f9731622', color: '#f97316' }}
            >
              Retried {step.retry_count}×
            </span>
          )}
          {typeof step.quality_score === 'number' && (isCompleted || isActive) && (
            <span className="flex items-center gap-1 text-xs" style={{ color: '#6B7280' }}>
              Quality {qualityDot(step.quality_score)}
            </span>
          )}
        </div>
        <p className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>{step.description}</p>

        {/* Pending with dependency info */}
        {statusLower === 'pending' && step.instructions && (
          <p className="text-xs mt-0.5 italic" style={{ color: '#6B7280' }}>
            Waiting to start
          </p>
        )}

        {/* Output expand */}
        {(isCompleted || isFailed) && (step.summary || (step.issues && step.issues.length > 0)) && (
          <ExpandSection label="View Output">
            {step.summary && (
              <p className="mb-1 whitespace-pre-wrap">{step.summary}</p>
            )}
            {step.issues && step.issues.length > 0 && (
              <div className="mt-1">
                <span style={{ color: '#ef4444' }}>Issues:</span>
                <ul className="list-disc ml-4 mt-0.5 space-y-0.5">
                  {step.issues.map((issue, i) => (
                    <li key={i} style={{ color: '#ef444499' }}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
          </ExpandSection>
        )}

        {/* Review expand */}
        {review && (
          <ExpandSection label="View Review">
            {typeof review.completeness_score === 'number' && (
              <div className="flex items-center gap-1 mb-1">
                <span style={{ color: '#6B7280' }}>Completeness:</span>
                <span className="font-semibold">{Math.round((review.completeness_score as number) * 100)}%</span>
                {qualityDot(review.completeness_score as number)}
              </div>
            )}
            {Array.isArray(review.gaps) && review.gaps.length > 0 && (
              <div className="mb-1">
                <span style={{ color: '#6B7280' }}>Gaps:</span>
                <ul className="list-disc ml-4 mt-0.5 space-y-0.5">
                  {(review.gaps as string[]).map((gap, i) => (
                    <li key={i}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
            {typeof review.should_retry === 'boolean' && (
              <div className="flex items-center gap-1">
                <span style={{ color: '#6B7280' }}>Should retry:</span>
                <span style={{ color: review.should_retry ? '#ef4444' : '#22c55e' }}>
                  {review.should_retry ? 'Yes' : 'No'}
                </span>
              </div>
            )}
          </ExpandSection>
        )}
      </div>
    </div>
  )
}

// ── Plan detail panel ─────────────────────────────────────────────────────────

function PlanDetailPanel({ planId, onClose }: { planId: string; onClose: () => void }) {
  const { data: detail, isLoading } = useQuery<PlanDetail>({
    queryKey: ['plan-detail', planId],
    queryFn: () => getPlanDetail(planId),
    refetchInterval: (query) => {
      const d = query.state.data
      if (!d) return 5000
      return d.status === 'IN_PROGRESS' ? 5000 : false
    },
  })

  return (
    <div
      className="rounded-lg border mt-2"
      style={{ background: '#0a1628', borderColor: '#f9731644' }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: '#1E3A5F' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <GitBranch size={14} style={{ color: '#f97316' }} className="shrink-0" />
          <span className="text-xs font-semibold text-white truncate">Plan Detail</span>
          <span className="font-mono text-xs shrink-0" style={{ color: '#6B7280' }}>
            {planId.slice(0, 8)}…
          </span>
          <CopyButton text={planId} />
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-300 transition-colors shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      {isLoading && (
        <div className="px-4 py-8 text-center text-xs" style={{ color: '#6B7280' }}>
          Loading plan…
        </div>
      )}

      {detail && (
        <div className="px-4 py-3 space-y-4">
          {/* Goal + meta */}
          <div>
            <p className="text-sm text-white leading-relaxed">{detail.goal}</p>
            <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs" style={{ color: '#6B7280' }}>
              <PlanStatusBadge status={detail.status} />
              {detail.execution_mode && (
                <span className="capitalize">{detail.execution_mode}</span>
              )}
              <span>{formatDate(detail.created_at)}</span>
              {detail.completed_at && (
                <span>Duration: {formatDurationFromDates(detail.created_at, detail.completed_at)}</span>
              )}
              {detail.duration_ms != null && !detail.completed_at && (
                <span>Duration: {formatDuration(detail.duration_ms)}</span>
              )}
            </div>
          </div>

          {/* Step timeline */}
          {detail.steps && detail.steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2" style={{ color: '#94A3B8' }}>
                Steps ({detail.steps_completed}/{detail.steps_total})
              </h4>
              <div
                className="rounded-lg border px-3"
                style={{ background: '#0f172a', borderColor: '#1E3A5F' }}
              >
                {detail.steps
                  .slice()
                  .sort((a, b) => a.step_number - b.step_number)
                  .map((step) => (
                    <PlanStepRow key={step.step_id} step={step} />
                  ))}
              </div>
            </div>
          )}

          {/* Final output */}
          {detail.status === 'COMPLETED' && detail.final_output && (
            <div>
              <h4 className="text-xs font-semibold mb-2" style={{ color: '#94A3B8' }}>
                Final Response
              </h4>
              <div
                className="p-3 rounded-lg text-sm leading-relaxed whitespace-pre-wrap"
                style={{
                  background: '#0f172a',
                  border: '1px solid #f9731633',
                  color: '#E2E8F0',
                }}
              >
                {detail.final_output}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Plan row ──────────────────────────────────────────────────────────────────

function PlanRow({ plan, onViewDetail, isExpanded }: {
  plan: Plan
  onViewDetail: () => void
  isExpanded: boolean
}) {
  const progressPct = plan.steps_total > 0
    ? Math.round((plan.steps_completed / plan.steps_total) * 100)
    : 0

  const agentLabels = plan.agents
    .map((a) => capitalizeFirst(stripAgentPrefix(a)))
    .join(', ')

  const duration = plan.completed_at
    ? formatDurationFromDates(plan.created_at, plan.completed_at)
    : plan.duration_ms
    ? formatDuration(plan.duration_ms)
    : ''

  const truncGoal = plan.goal.length > 60 ? plan.goal.slice(0, 60) + '…' : plan.goal

  return (
    <div
      className="rounded-lg border p-4 transition-all"
      style={{
        background: '#0f172a',
        borderColor: plan.status === 'IN_PROGRESS' ? '#f9731644' : isExpanded ? '#f9731622' : '#1E3A5F',
      }}
    >
      {/* Main row */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2 flex-wrap">
            <PlanStatusBadge status={plan.status} />
            <p className="text-sm text-white leading-snug" title={plan.goal}>
              {truncGoal}
            </p>
          </div>

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs" style={{ color: '#6B7280' }}>
            <span>Steps: <span className="text-white font-medium">{plan.steps_completed}/{plan.steps_total}</span></span>
            {agentLabels && <span>Agents: {agentLabels}</span>}
            <span>{formatDate(plan.created_at)}</span>
            {duration && <span>Duration: {duration}</span>}
          </div>

          {/* Progress bar */}
          {plan.steps_total > 0 && (
            <div className="mt-2 max-w-xs">
              <ProgressBar value={progressPct} />
            </div>
          )}
        </div>

        <button
          onClick={onViewDetail}
          className="shrink-0 text-xs px-3 py-1 rounded border transition-colors"
          style={{
            borderColor: isExpanded ? '#f97316' : '#1E3A5F',
            color: isExpanded ? '#f97316' : '#94A3B8',
          }}
        >
          {isExpanded ? 'Hide Detail' : 'View Detail'}
        </button>
      </div>
    </div>
  )
}

// ── Plans tab ─────────────────────────────────────────────────────────────────

function PlansTab() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null)

  const { data: plans, isLoading, isError, refetch } = useQuery<Plan[]>({
    queryKey: ['plans', statusFilter],
    queryFn: () => getPlans(undefined, statusFilter || undefined, 20),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 10000
      const hasActive = data.some((p) => p.status === 'IN_PROGRESS')
      return hasActive ? 5000 : false
    },
  })

  const handleToggleDetail = useCallback((planId: string) => {
    setExpandedPlanId((prev) => (prev === planId ? null : planId))
  }, [])

  const planList = plans ?? []

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-xs px-3 py-1.5 rounded-lg border outline-none"
          style={{ background: '#1E293B', borderColor: '#1E3A5F', color: '#94A3B8' }}
        >
          <option value="">All Status</option>
          <option value="PENDING">Pending</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
        </select>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors"
          style={{ borderColor: '#1E3A5F', color: '#94A3B8' }}
          title="Refresh plans"
        >
          <RefreshCw size={11} />
          Refresh
        </button>
      </div>

      {isError && (
        <div className="text-center py-16" style={{ color: '#ef4444' }}>
          <p className="text-sm">Could not load plans. Check that the API server is running.</p>
        </div>
      )}

      {isLoading && (
        <div className="text-center py-16" style={{ color: '#6B7280' }}>
          <RefreshCw size={20} className="mx-auto mb-2 animate-spin opacity-50" />
          <p className="text-sm">Loading plans…</p>
        </div>
      )}

      {!isLoading && !isError && planList.length === 0 && (
        <div className="text-center py-16" style={{ color: '#6B7280' }}>
          <GitBranch size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No agent plans yet. Plans are created when multi-agent tasks run.</p>
        </div>
      )}

      {!isLoading && !isError && planList.length > 0 && (
        <div className="space-y-3">
          {planList.map((plan) => (
            <div key={plan.plan_id}>
              <PlanRow
                plan={plan}
                onViewDetail={() => handleToggleDetail(plan.plan_id)}
                isExpanded={expandedPlanId === plan.plan_id}
              />
              {expandedPlanId === plan.plan_id && (
                <PlanDetailPanel
                  planId={plan.plan_id}
                  onClose={() => setExpandedPlanId(null)}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────

type Tab = 'active' | 'scheduled' | 'plans'

export default function BackgroundTasksPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('active')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [agentFilter, setAgentFilter] = useState<string>('')
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Stats
  const { data: statsData } = useQuery<TaskStats>({
    queryKey: ['task-stats'],
    queryFn: () => portalApi.getTaskStats().then((r) => r.data),
    refetchInterval: autoRefresh ? 10000 : false,
  })
  const stats: TaskStats = statsData ?? { all: 0, queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 }

  // Active tasks
  const {
    data: tasksData,
    isError: tasksError,
  } = useQuery({
    queryKey: ['bg-tasks', statusFilter],
    queryFn: () =>
      portalApi.getTasks(1, statusFilter || undefined).then((r) => r.data),
    refetchInterval: autoRefresh ? 10000 : false,
  })
  const tasks: AgentTask[] = tasksData?.tasks ?? []

  // Scheduled tasks
  const { data: scheduledData } = useQuery({
    queryKey: ['scheduled-tasks-admin'],
    queryFn: () => portalApi.getScheduledTasksAdmin().then((r) => r.data),
    refetchInterval: autoRefresh ? 30000 : false,
  })
  const scheduledJobs: ScheduledJob[] = scheduledData?.jobs ?? []

  // Mutations
  const killMutation = useMutation({
    mutationFn: (taskId: string) => portalApi.killTask(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bg-tasks'] }),
  })
  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => portalApi.deleteTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bg-tasks'] })
      qc.invalidateQueries({ queryKey: ['task-stats'] })
    },
  })
  const runMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.runScheduledTask(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bg-tasks'] })
      qc.invalidateQueries({ queryKey: ['task-stats'] })
      setTab('active')
    },
  })
  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.pauseScheduledTask(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled-tasks-admin'] }),
  })
  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.resumeScheduledTask(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled-tasks-admin'] }),
  })

  // Filter tasks
  const filteredTasks = tasks.filter((t) => {
    const normalizedStatus = t.status === 'revoked' ? 'cancelled' : t.status
    if (statusFilter && normalizedStatus !== statusFilter) return false
    if (agentFilter && t.department !== agentFilter) return false
    return true
  })

  // Unique agents for filter
  const agents = Array.from(new Set(tasks.map((t) => t.department).filter(Boolean))) as string[]

  const TAB_LABELS: Record<Tab, string> = {
    active: 'Active Tasks',
    scheduled: 'Scheduled Tasks',
    plans: 'Agent Plans',
  }

  return (
    <div className="flex flex-col h-full" style={{ background: '#0f172a', color: 'white' }}>
      {/* Header */}
      <div className="px-6 py-5 border-b" style={{ borderColor: '#1E3A5F' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity size={20} style={{ color: '#f97316' }} />
            <h1 className="text-lg font-semibold">Tasks</h1>
          </div>
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-colors ${autoRefresh ? 'text-orange-400 border-orange-500/40' : 'text-gray-500 border-gray-700'}`}
          >
            <RefreshCw size={12} className={autoRefresh ? 'animate-spin' : ''} style={autoRefresh ? { animationDuration: '3s' } : {}} />
            Auto-refresh {autoRefresh ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* Stats row */}
        <div className="flex flex-wrap gap-2 mt-4">
          <StatPill label="All" value={stats.all} />
          <StatPill label="Running" value={stats.running} color="#f97316" />
          <StatPill label="Queued" value={stats.queued} color="#94A3B8" />
          <StatPill label="Completed" value={stats.completed} color="#22c55e" />
          <StatPill label="Failed" value={stats.failed} color="#ef4444" />
          <StatPill label="Cancelled" value={stats.cancelled} color="#6B7280" />
        </div>
      </div>

      {/* Tabs */}
      <div className="px-6 border-b flex gap-0" style={{ borderColor: '#1E3A5F' }}>
        {(['active', 'scheduled', 'plans'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm border-b-2 transition-colors ${tab === t ? 'font-medium' : 'text-gray-500 border-transparent hover:text-gray-300'}`}
            style={tab === t ? { borderColor: '#f97316', color: '#f97316' } : {}}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {tab === 'active' && (
          <>
            {/* Filters */}
            <div className="flex gap-3 mb-4">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="text-xs px-3 py-1.5 rounded-lg border outline-none"
                style={{ background: '#1E293B', borderColor: '#1E3A5F', color: '#94A3B8' }}
              >
                <option value="">All Status</option>
                <option value="queued">Pending</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              {agents.length > 0 && (
                <select
                  value={agentFilter}
                  onChange={(e) => setAgentFilter(e.target.value)}
                  className="text-xs px-3 py-1.5 rounded-lg border outline-none capitalize"
                  style={{ background: '#1E293B', borderColor: '#1E3A5F', color: '#94A3B8' }}
                >
                  <option value="">All Agents</option>
                  {agents.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Task list */}
            {tasksError ? (
              <div className="text-center py-16" style={{ color: '#ef4444' }}>
                <p className="text-sm">Could not connect to task queue. Check that the Celery worker is running.</p>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="text-center py-16" style={{ color: '#6B7280' }}>
                <Activity size={32} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">No background tasks yet. Tasks created by agents will appear here.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onKill={(id) => killMutation.mutate(id)}
                    onDelete={(id) => deleteMutation.mutate(id)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'scheduled' && (
          <>
            {scheduledJobs.length === 0 ? (
              <div className="text-center py-16" style={{ color: '#6B7280' }}>
                <p className="text-sm">No scheduled jobs found.</p>
              </div>
            ) : (
              <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1E3A5F' }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-left" style={{ background: '#1E293B', color: '#6B7280' }}>
                      <th className="px-4 py-3 font-medium">Job Name</th>
                      <th className="px-4 py-3 font-medium">Agent</th>
                      <th className="px-4 py-3 font-medium">Schedule</th>
                      <th className="px-4 py-3 font-medium">Next Run</th>
                      <th className="px-4 py-3 font-medium">Last Run</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scheduledJobs.map((job) => (
                      <ScheduledJobRow
                        key={job.id}
                        job={job}
                        onRun={(id) => runMutation.mutate(id)}
                        onPause={(id) => pauseMutation.mutate(id)}
                        onResume={(id) => resumeMutation.mutate(id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {tab === 'plans' && <PlansTab />}
      </div>
    </div>
  )
}
