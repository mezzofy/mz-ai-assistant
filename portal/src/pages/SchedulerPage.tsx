import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { portalApi } from '../api/portal'
import type { ScheduledJob } from '../types'

const AGENT_OPTIONS = ['finance', 'sales', 'marketing', 'support', 'management', 'hr']

const EMPTY_CREATE_FORM = { name: '', agent: 'sales', message: '', schedule: '', workflow_name: '' }

export default function SchedulerPage() {
  const qc = useQueryClient()
  const [selectedJob, setSelectedJob] = useState<ScheduledJob | null>(null)
  const [toast, setToast] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState<{ name: string; schedule: string; agent: string; workflow_name: string }>({ name: '', schedule: '', agent: '', workflow_name: '' })

  // Create job state
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE_FORM)
  const [createError, setCreateError] = useState('')

  // Delete job state
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null)

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

  const updateJobMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, string> }) =>
      portalApi.updateJob(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      setEditMode(false)
    },
  })

  const createJobMutation = useMutation({
    mutationFn: (data: typeof createForm) => portalApi.createJob(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      setShowCreateForm(false)
      setCreateForm(EMPTY_CREATE_FORM)
      setCreateError('')
      setToast('Job created successfully')
      setTimeout(() => setToast(''), 4000)
    },
  })

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => portalApi.deleteJob(jobId),
    onSuccess: (_, jobId) => {
      qc.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      if (selectedJob?.id === jobId) setSelectedJob(null)
      setDeletingJobId(null)
      setToast('Job deleted')
      setTimeout(() => setToast(''), 3000)
    },
  })

  useEffect(() => {
    if (selectedJob) {
      setEditForm({
        name: selectedJob.name,
        schedule: selectedJob.schedule,
        agent: selectedJob.agent || '',
        workflow_name: selectedJob.workflow_name || '',
      })
      setEditMode(false)
    }
  }, [selectedJob])

  const jobs: ScheduledJob[] = data?.jobs || []

  function handleCreateSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!createForm.name.trim() || !createForm.message.trim() || !createForm.schedule.trim()) {
      setCreateError('Name, Message, and Schedule are required.')
      return
    }
    setCreateError('')
    createJobMutation.mutate(createForm)
  }

  function handleCancelCreate() {
    setShowCreateForm(false)
    setCreateForm(EMPTY_CREATE_FORM)
    setCreateError('')
  }

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Scheduler
        </h1>
        <button
          onClick={() => { setShowCreateForm(true); setDeletingJobId(null) }}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90"
          style={{ background: '#f97316' }}
        >
          + New Job
        </button>
      </div>

      {toast && (
        <div
          className="px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(0, 212, 170, 0.15)', color: '#00D4AA', borderLeft: '3px solid #00D4AA' }}
        >
          ✓ {toast}
        </div>
      )}

      {/* Create Job Form */}
      {showCreateForm && (
        <div className="rounded-xl border p-5 space-y-4" style={{ background: '#111827', borderColor: '#f97316' }}>
          <div className="text-sm font-semibold text-white">Create New Job</div>
          <form onSubmit={handleCreateSubmit} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Name */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Name <span style={{ color: '#f97316' }}>*</span></label>
                <input
                  value={createForm.name}
                  onChange={(e) => setCreateForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Daily Sales Report"
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                />
              </div>
              {/* Agent */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Agent <span style={{ color: '#f97316' }}>*</span></label>
                <select
                  value={createForm.agent}
                  onChange={(e) => setCreateForm(f => ({ ...f, agent: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  {AGENT_OPTIONS.map(a => (
                    <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Message */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Message <span style={{ color: '#f97316' }}>*</span></label>
              <textarea
                rows={3}
                value={createForm.message}
                onChange={(e) => setCreateForm(f => ({ ...f, message: e.target.value }))}
                placeholder="What should the agent do?"
                className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none resize-none"
                style={{ background: '#1E2A3A', borderColor: '#374151' }}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Schedule */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Schedule <span style={{ color: '#f97316' }}>*</span></label>
                <input
                  value={createForm.schedule}
                  onChange={(e) => setCreateForm(f => ({ ...f, schedule: e.target.value }))}
                  placeholder="0 9 * * 1-5"
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none font-mono"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                />
                <p className="text-xs mt-1" style={{ color: '#6B7280' }}>Cron: min hour day month weekday</p>
              </div>
              {/* Workflow Name */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Workflow Name <span style={{ color: '#6B7280' }}>(optional)</span></label>
                <input
                  value={createForm.workflow_name}
                  onChange={(e) => setCreateForm(f => ({ ...f, workflow_name: e.target.value }))}
                  placeholder="e.g. weekly-report"
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                />
              </div>
            </div>

            {createError && (
              <p className="text-xs" style={{ color: '#EF4444' }}>{createError}</p>
            )}

            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={createJobMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
                style={{ background: '#f97316' }}
              >
                {createJobMutation.isPending ? 'Creating...' : 'Create'}
              </button>
              <button
                type="button"
                onClick={handleCancelCreate}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
                style={{ background: '#1E2A3A' }}
              >
                Cancel
              </button>
            </div>
          </form>
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
                  <React.Fragment key={job.id}>
                    <tr
                      className="border-t cursor-pointer hover:bg-white/5 transition-colors"
                      style={{
                        borderColor: '#1E2A3A',
                        background: selectedJob?.id === job.id ? 'rgba(249, 115, 22, 0.08)' : undefined,
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
                        <div className="flex gap-1 items-center">
                          <button
                            onClick={(e) => { e.stopPropagation(); triggerMutation.mutate(job.id) }}
                            className="px-2 py-1 rounded text-xs transition-colors hover:bg-indigo-500/20"
                            style={{ color: '#f97316' }}
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
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeletingJobId(job.id)
                              setShowCreateForm(false)
                            }}
                            className="px-2 py-1 rounded text-xs transition-colors hover:bg-red-500/20"
                            style={{ color: '#ef4444' }}
                            title="Delete job"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {/* Inline delete confirmation */}
                    {deletingJobId === job.id && (
                      <tr style={{ borderColor: '#1E2A3A' }} className="border-t">
                        <td colSpan={6} className="px-4 py-3">
                          <div
                            className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs"
                            style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                          >
                            <span style={{ color: '#F87171' }}>Delete <strong className="text-white">{job.name}</strong>? This cannot be undone.</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteJobMutation.mutate(job.id) }}
                              disabled={deleteJobMutation.isPending}
                              className="px-3 py-1 rounded-md font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
                              style={{ background: '#ef4444' }}
                            >
                              {deleteJobMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); setDeletingJobId(null) }}
                              className="px-3 py-1 rounded-md text-gray-400 hover:text-white transition-colors"
                              style={{ background: '#1E2A3A' }}
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
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

        {/* Job Detail + Edit + History */}
        <div className="lg:col-span-2 space-y-4">
          {/* Job Detail Card */}
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <div className="p-4 border-b flex items-center justify-between text-sm font-medium text-gray-300" style={{ borderColor: '#1E2A3A' }}>
              <span>{selectedJob ? selectedJob.name : 'Select a job'}</span>
              {selectedJob && !editMode && (
                <button
                  onClick={() => setEditMode(true)}
                  className="px-3 py-1 rounded-lg text-xs transition-all"
                  style={{ background: '#1E2A3A', color: '#f97316' }}
                >
                  Edit
                </button>
              )}
            </div>
            {selectedJob && (
              <div className="p-4 space-y-3 text-xs">
                {editMode ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-gray-400 mb-1">Name</label>
                      <input
                        value={editForm.name}
                        onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                        style={{ background: '#1E2A3A', borderColor: '#374151' }}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 mb-1">Schedule (cron)</label>
                      <input
                        value={editForm.schedule}
                        onChange={(e) => setEditForm(f => ({ ...f, schedule: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none font-mono"
                        style={{ background: '#1E2A3A', borderColor: '#374151' }}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 mb-1">Agent</label>
                      <input
                        value={editForm.agent}
                        onChange={(e) => setEditForm(f => ({ ...f, agent: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                        style={{ background: '#1E2A3A', borderColor: '#374151' }}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 mb-1">Workflow Name</label>
                      <input
                        value={editForm.workflow_name}
                        onChange={(e) => setEditForm(f => ({ ...f, workflow_name: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                        style={{ background: '#1E2A3A', borderColor: '#374151' }}
                      />
                    </div>
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => updateJobMutation.mutate({ id: selectedJob.id, data: editForm })}
                        disabled={updateJobMutation.isPending}
                        className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
                        style={{ background: '#f97316' }}
                      >
                        {updateJobMutation.isPending ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={() => setEditMode(false)}
                        className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                    <div>
                      <span className="text-gray-500">Schedule</span>
                      <div className="text-gray-200 font-mono">{selectedJob.schedule}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Agent</span>
                      <div className="text-gray-200">{selectedJob.agent || '\u2014'}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Workflow</span>
                      <div className="text-gray-200">{selectedJob.workflow_name || '\u2014'}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Owner</span>
                      <div className="text-gray-200">{selectedJob.user_email}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Next Run</span>
                      <div className="text-gray-200">{selectedJob.next_run ? new Date(selectedJob.next_run).toLocaleString() : '\u2014'}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Last Run</span>
                      <div className="text-gray-200">{selectedJob.last_run ? new Date(selectedJob.last_run).toLocaleString() : '\u2014'}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Status</span>
                      <div>
                        <span
                          className="px-2 py-0.5 rounded-full"
                          style={{
                            background: selectedJob.is_active ? 'rgba(0, 212, 170, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                            color: selectedJob.is_active ? '#00D4AA' : '#6B7280',
                          }}
                        >
                          {selectedJob.is_active ? 'Active' : 'Paused'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Run History */}
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <div className="p-4 border-b text-sm font-medium text-gray-300" style={{ borderColor: '#1E2A3A' }}>
              Run History
            </div>
            <div className="p-4 space-y-2 overflow-y-auto max-h-64">
              {history?.history?.map((run: { id: string; status: string; started_at?: string; duration_ms?: number }) => (
                <div key={run.id} className="flex items-start gap-3 text-xs">
                  <span
                    className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                    style={{ background: run.status === 'completed' ? '#00D4AA' : run.status === 'running' ? '#f97316' : '#EF4444' }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between">
                      <span className="text-gray-300">
                        {run.started_at ? new Date(run.started_at).toLocaleString() : '\u2014'}
                      </span>
                      {run.duration_ms && (
                        <span style={{ color: '#6B7280' }}>{(run.duration_ms / 1000).toFixed(1)}s</span>
                      )}
                    </div>
                    <div style={{ color: run.status === 'completed' ? '#00D4AA' : run.status === 'running' ? '#f97316' : '#EF4444' }}>
                      {run.status}
                    </div>
                  </div>
                </div>
              ))}
              {selectedJob && !history?.history?.length && (
                <p className="text-xs text-center py-8" style={{ color: '#6B7280' }}>No run history</p>
              )}
              {!selectedJob && (
                <p className="text-xs text-center py-8" style={{ color: '#6B7280' }}>Select a job to view history</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
