import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { AgentTask } from '../types'

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      }}
      className="ml-1.5 text-xs px-1.5 py-0.5 rounded transition-colors"
      style={{ background: '#1E2A3A', color: copied ? '#00D4AA' : '#6B7280' }}
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export default function TasksPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [deptFilter, setDeptFilter] = useState<string>('')
  const [triggeredByFilter, setTriggeredByFilter] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks', page, statusFilter],
    queryFn: () => portalApi.getTasks(page, statusFilter || undefined).then(r => r.data),
    refetchInterval: 10000,
  })

  const tasks: AgentTask[] = data?.tasks || []
  const totalPages = data?.total_pages || 1

  const departments = Array.from(new Set(tasks.map(t => t.department).filter(Boolean))) as string[]
  const triggeredByUsers = Array.from(
    new Set(tasks.map(t => t.triggered_by_name || t.triggered_by_email?.split('@')[0]).filter(Boolean))
  ) as string[]

  const filteredTasks = tasks.filter(t => {
    if (deptFilter && t.department !== deptFilter) return false
    if (triggeredByFilter) {
      const label = t.triggered_by_name || t.triggered_by_email?.split('@')[0] || ''
      if (label !== triggeredByFilter) return false
    }
    return true
  })

  const statusColor = (s: string) => {
    if (s === 'completed') return { background: 'rgba(0,212,170,0.1)', color: '#00D4AA' }
    if (s === 'running') return { background: 'rgba(249,115,22,0.1)', color: '#f97316' }
    return { background: 'rgba(239,68,68,0.1)', color: '#EF4444' }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Messages
          </h1>
          <span className="text-sm" style={{ color: '#6B7280' }}>
            {data?.total !== undefined ? `${data.total} total` : ''}
          </span>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          {['', 'running', 'completed', 'failed'].map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1) }}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
              style={{
                background: statusFilter === s ? '#f97316' : '#1E2A3A',
                color: statusFilter === s ? 'white' : '#6B7280',
              }}
            >
              {s || 'All'}
            </button>
          ))}
          <select
            value={deptFilter}
            onChange={(e) => { setDeptFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: '#1E2A3A', color: '#6B7280', border: 'none' }}
          >
            <option value="">All Depts</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <select
            value={triggeredByFilter}
            onChange={(e) => { setTriggeredByFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: '#1E2A3A', color: '#6B7280', border: 'none' }}
          >
            <option value="">All Users</option>
            {triggeredByUsers.map(u => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' }}>
          Failed to load tasks: {(error as { message?: string }).message || 'Unknown error'}
          <span className="ml-2 text-xs opacity-60">(Check server logs for details)</span>
        </div>
      )}

      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
              <th className="px-4 py-3">Message ID</th>
              <th className="py-3">Content</th>
              <th className="py-3">Dept</th>
              <th className="py-3">Status</th>
              <th className="py-3">Triggered By</th>
              <th className="py-3">Created</th>
              <th className="py-3 pr-4">Duration</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>Loading...</td></tr>
            )}
            {filteredTasks.map((t) => {
              const sc = statusColor(t.status)
              return (
                <React.Fragment key={t.id}>
                  <tr
                    className="border-t cursor-pointer hover:bg-white/[0.02] transition-colors"
                    style={{ borderColor: '#1E2A3A' }}
                    onClick={() => setExpandedId(id => id === t.id ? null : t.id)}
                  >
                    <td className="px-4 py-2.5 font-mono" style={{ color: '#6B7280' }}>
                      {t.id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 max-w-[200px]">
                      <span className="text-gray-200 truncate block" title={t.content || undefined}>{t.content || '\u2014'}</span>
                      {t.error && <span className="text-xs text-red-400 truncate block" title={t.error}>{t.error.slice(0, 60)}</span>}
                    </td>
                    <td className="py-2.5 text-gray-400">{t.department || '\u2014'}</td>
                    <td className="py-2.5">
                      <span className="px-2 py-0.5 rounded-full text-xs" style={sc}>
                        {t.status}
                      </span>
                    </td>
                    <td className="py-2.5 text-gray-400">
                      {t.triggered_by_name || t.triggered_by_email?.split('@')[0] || '\u2014'}
                    </td>
                    <td className="py-2.5 text-gray-400">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : '\u2014'}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-400 font-mono">
                      {t.duration_ms ? `${(t.duration_ms / 1000).toFixed(1)}s` : '\u2014'}
                    </td>
                  </tr>
                  {expandedId === t.id && (
                    <tr style={{ borderColor: '#1E2A3A' }}>
                      <td colSpan={7} className="px-4 pb-3" style={{ background: '#0A0E1A' }}>
                        <div className="pt-2 space-y-2">
                          {/* Full Task ID */}
                          <div className="flex items-center text-xs" style={{ color: '#6B7280' }}>
                            <span>Message ID:</span>
                            <span className="ml-1.5 font-mono" style={{ color: '#94A3B8' }}>{t.id}</span>
                            <CopyBtn text={t.id} />
                          </div>
                          {/* Full error */}
                          {t.error && (
                            <div className="text-xs font-mono p-2 rounded" style={{ background: '#1E0A0A', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                              {t.error}
                            </div>
                          )}
                          {/* Raw result */}
                          {t.details && (
                            <div className="space-y-2">
                              {typeof (t.details as Record<string, unknown>).response === 'string' && (
                                <div>
                                  <div className="text-xs mb-1" style={{ color: '#6B7280' }}>Response</div>
                                  <div
                                    className="text-xs p-2 rounded"
                                    style={{
                                      background: '#1E293B',
                                      color: '#E2E8F0',
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                      maxHeight: '300px',
                                      overflowY: 'auto',
                                    }}
                                  >
                                    {(t.details as Record<string, unknown>).response as string}
                                  </div>
                                </div>
                              )}
                              <details>
                                <summary className="text-xs cursor-pointer select-none" style={{ color: '#6B7280' }}>
                                  Raw JSON
                                </summary>
                                <pre className="mt-1 p-2 rounded overflow-x-auto text-xs font-mono"
                                  style={{ background: '#1E293B', color: '#94A3B8', maxHeight: '200px', overflowY: 'auto' }}>
                                  {JSON.stringify(t.details, null, 2)}
                                </pre>
                              </details>
                            </div>
                          )}
                          {!t.error && !t.details && (
                            <span className="text-xs" style={{ color: '#6B7280' }}>No result data available.</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
            {!isLoading && filteredTasks.length === 0 && (
              <tr><td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>No messages</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs" style={{ color: '#6B7280' }}>
          <span>Page {page} of {totalPages} · {data?.total || 0} total messages</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 rounded-lg transition-all disabled:opacity-40"
              style={{ background: '#1E2A3A', color: '#E5E7EB' }}
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 rounded-lg transition-all disabled:opacity-40"
              style={{ background: '#1E2A3A', color: '#E5E7EB' }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
