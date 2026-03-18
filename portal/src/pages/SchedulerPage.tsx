import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { ScheduledJob } from '../types'

export default function SchedulerPage() {
  const qc = useQueryClient()
  const [selectedJob, setSelectedJob] = useState<ScheduledJob | null>(null)
  const [toast, setToast] = useState('')

  const { data } = useQuery({
    queryKey: ['scheduler-jobs'],
    queryFn: () => portalApi.getJobs().then((r) => r.data),
    refetchInterval: 30000,
  })

  const { data: history } = useQuery({
    queryKey: ['job-history', selectedJob?.id],
    queryFn: () => selectedJob ? portalApi.getJobHistory(selectedJob.id).then((r) => r.data) : null,
    enabled: !!selectedJob,
  })

  const triggerMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.triggerJob(jobId),
    onSuccess: (res) => {
      setToast(`Task queued: ${res.data.task_id.slice(0, 8)}...`)
      setTimeout(() => setToast(''), 4000)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.toggleJob(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler-jobs'] }),
  })

  const jobs: ScheduledJob[] = data?.jobs || []

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        Scheduler
      </h1>

      {toast && (
        <div
          className="px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(0, 212, 170, 0.15)', color: '#00D4AA', borderLeft: '3px solid #00D4AA' }}
        >
          ✓ {toast}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Jobs table */}
        <div className="lg:col-span-3 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <div className="p-4 border-b text-sm font-medium text-gray-300" style={{ borderColor: '#1E2A3A' }}>
            Scheduled Jobs ({jobs.length})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ color: '#6B7280' }} className="border-b">
                  <th className="text-left px-4 py-2">Name</th>
                  <th className="text-left py-2">Owner</th>
                  <th className="text-left py-2">Schedule</th>
                  <th className="text-left py-2">Next Run</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-t cursor-pointer hover:bg-white/5 transition-colors"
                    style={{
                      borderColor: '#1E2A3A',
                      background: selectedJob?.id === job.id ? 'rgba(108, 99, 255, 0.08)' : undefined,
                    }}
                    onClick={() => setSelectedJob(job)}
                  >
                    <td className="px-4 py-2.5 text-gray-200 font-medium">{job.name}</td>
                    <td className="py-2.5 text-gray-400">{job.user_email.split('@')[0]}</td>
                    <td className="py-2.5 font-mono text-gray-300">{job.schedule}</td>
                    <td className="py-2.5 text-gray-400">
                      {job.next_run ? new Date(job.next_run).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2.5">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs"
                        style={{
                          background: job.is_active ? 'rgba(0, 212, 170, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                          color: job.is_active ? '#00D4AA' : '#6B7280',
                        }}
                      >
                        {job.is_active ? 'Active' : 'Paused'}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); triggerMutation.mutate(job.id) }}
                          className="px-2 py-1 rounded text-xs transition-colors hover:bg-indigo-500/20"
                          style={{ color: '#6C63FF' }}
                          title="Run now"
                        >
                          ▶
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleMutation.mutate(job.id) }}
                          className="px-2 py-1 rounded text-xs transition-colors"
                          style={{ color: job.is_active ? '#F59E0B' : '#00D4AA' }}
                          title={job.is_active ? 'Pause' : 'Resume'}
                        >
                          {job.is_active ? '⏸' : '▶'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-12 text-center" style={{ color: '#6B7280' }}>
                      No scheduled jobs
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Run history */}
        <div className="lg:col-span-2 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <div className="p-4 border-b text-sm font-medium text-gray-300" style={{ borderColor: '#1E2A3A' }}>
            {selectedJob ? `History: ${selectedJob.name}` : 'Select a job to view history'}
          </div>
          <div className="p-4 space-y-2 overflow-y-auto max-h-96">
            {history?.history?.map((run: { id: string; status: string; started_at?: string; duration_ms?: number }) => (
              <div key={run.id} className="flex items-start gap-3 text-xs">
                <span
                  className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                  style={{ background: run.status === 'completed' ? '#00D4AA' : run.status === 'running' ? '#6C63FF' : '#EF4444' }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between">
                    <span className="text-gray-300">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                    </span>
                    {run.duration_ms && (
                      <span style={{ color: '#6B7280' }}>{(run.duration_ms / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                  <div style={{ color: run.status === 'completed' ? '#00D4AA' : run.status === 'running' ? '#6C63FF' : '#EF4444' }}>
                    {run.status}
                  </div>
                </div>
              </div>
            ))}
            {selectedJob && !history?.history?.length && (
              <p className="text-xs text-center py-8" style={{ color: '#6B7280' }}>No run history</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
