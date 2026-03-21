import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { AgentTask } from '../types'

export default function TasksPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks', page, statusFilter],
    queryFn: () => portalApi.getTasks(page, statusFilter || undefined).then(r => r.data),
    refetchInterval: 10000,
  })

  const killMutation = useMutation({
    mutationFn: (taskId: string) => portalApi.killTask(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const tasks: AgentTask[] = data?.tasks || []
  const totalPages = data?.total_pages || 1

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
        <div className="flex gap-2">
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
              <th className="py-3">Duration</th>
              <th className="py-3 pr-4">Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} className="py-12 text-center" style={{ color: '#6B7280' }}>Loading...</td></tr>
            )}
            {tasks.map((t) => {
              const sc = statusColor(t.status)
              return (
                <tr key={t.id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
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
                  <td className="py-2.5 text-gray-400 font-mono">
                    {t.duration_ms ? `${(t.duration_ms / 1000).toFixed(1)}s` : '\u2014'}
                  </td>
                  <td className="py-2.5 pr-4">
                    {t.status === 'running' && (
                      <button
                        onClick={() => killMutation.mutate(t.id)}
                        disabled={killMutation.isPending}
                        title="Kill task"
                        className="p-1.5 rounded transition-colors hover:bg-red-500/20 disabled:opacity-40"
                        style={{ color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)' }}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        </svg>
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {!isLoading && tasks.length === 0 && (
              <tr><td colSpan={8} className="py-12 text-center" style={{ color: '#6B7280' }}>No messages</td></tr>
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
