import React, { useState, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { Agent } from '../types'

export default function AgentsPage() {
  const qc = useQueryClient()
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [memoryData, setMemoryData] = useState<Record<string, { filename: string; size_bytes: number }[]>>({})
  const [uploadingFor, setUploadingFor] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const { data } = useQuery({
    queryKey: ['agents'],
    queryFn: () => portalApi.getAgents().then((r) => r.data),
    refetchInterval: 10000,
  })

  const agents: Agent[] = data?.agents || []

  const loadMemory = async (dept: string) => {
    if (expandedAgent === dept) {
      setExpandedAgent(null)
      return
    }
    setExpandedAgent(dept)
    if (!memoryData[dept]) {
      const res = await portalApi.getAgentMemory(dept)
      setMemoryData((prev) => ({ ...prev, [dept]: res.data.files }))
    }
  }

  const refreshMemory = async (dept: string) => {
    const res = await portalApi.getAgentMemory(dept)
    setMemoryData((prev) => ({ ...prev, [dept]: res.data.files }))
    qc.invalidateQueries({ queryKey: ['agents'] })
  }

  const handleUpload = async (dept: string, file: File) => {
    setUploadingFor(dept)
    setUploadError(null)
    try {
      await portalApi.uploadAgentMemory(dept, file)
      await refreshMemory(dept)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      setUploadError(e.response?.data?.detail || e.message || 'Upload failed')
    } finally {
      setUploadingFor(null)
    }
  }

  const handleDeleteMemory = async (dept: string, filename: string) => {
    try {
      await portalApi.deleteAgentMemory(dept, filename)
      await refreshMemory(dept)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      setUploadError(e.response?.data?.detail || e.message || 'Delete failed')
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        Agents
      </h1>

      {uploadError && (
        <div className="px-4 py-2 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' }}>
          {uploadError}
          <button onClick={() => setUploadError(null)} className="ml-2 text-xs opacity-60 hover:opacity-100">&#10005;</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <div
            key={agent.department}
            className="rounded-xl border p-5 flex flex-col gap-3"
            style={{ background: '#111827', borderColor: '#1E2A3A' }}
          >
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ background: agent.is_busy ? '#00D4AA' : '#374151' }}
                  />
                  <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
                  {agent.is_orchestrator && (
                    <span
                      className="px-1.5 py-0.5 rounded text-xs font-bold"
                      style={{ background: 'rgba(108,99,255,0.15)', color: '#6C63FF', border: '1px solid rgba(108,99,255,0.3)' }}
                    >
                      ORCHESTRATOR
                    </span>
                  )}
                  {!agent.is_orchestrator && ['research', 'developer', 'scheduler', 'legal'].includes(agent.department) && (
                    <span
                      className="px-1.5 py-0.5 rounded text-xs font-bold"
                      style={{ background: 'rgba(0,212,170,0.1)', color: '#00D4AA', border: '1px solid rgba(0,212,170,0.2)' }}
                    >
                      SPECIAL
                    </span>
                  )}
                </div>
                {agent.persona && (
                  <div className="text-xs mt-0.5" style={{ color: '#f97316' }}>
                    {agent.persona} · {agent.department}
                  </div>
                )}
              </div>
              <div className="text-right ml-2 flex-shrink-0">
                <div className="text-lg font-bold" style={{ color: '#f97316' }}>
                  {agent.tasks_today}
                </div>
                <div className="text-xs" style={{ color: '#6B7280' }}>today</div>
              </div>
            </div>

            {/* Description */}
            {agent.description && (
              <p className="text-xs leading-relaxed line-clamp-2" style={{ color: '#9CA3AF' }}>
                {agent.description}
              </p>
            )}

            {/* Skills */}
            {agent.skills.length > 0 && (
              <div>
                <div className="text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Skills</div>
                <div className="flex flex-wrap gap-1">
                  {agent.skills.map((skill) => (
                    <span
                      key={skill}
                      className="px-2 py-0.5 rounded text-xs"
                      style={{ background: '#1E2A3A', color: '#9CA3AF' }}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tools */}
            {agent.tools_allowed && agent.tools_allowed.length > 0 && (
              <div>
                <div className="text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Tools</div>
                <div className="flex flex-wrap gap-1">
                  {agent.tools_allowed.map((tool) => (
                    <span
                      key={tool}
                      className="px-2 py-0.5 rounded text-xs"
                      style={{ background: 'rgba(249,115,22,0.08)', color: '#f97316', border: '1px solid rgba(249,115,22,0.15)' }}
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Footer: LLM model + Memory toggle */}
            <div className="flex items-center justify-between border-t pt-2" style={{ borderColor: '#1E2A3A' }}>
              {agent.llm_model && (
                <span className="text-xs font-mono" style={{ color: '#6B7280' }}>
                  {agent.llm_model}
                </span>
              )}
              <button
                onClick={() => loadMemory(agent.department)}
                className="flex items-center gap-1 text-xs transition-colors hover:text-orange-400 ml-auto"
                style={{ color: '#6B7280' }}
              >
                <span>Memory ({agent.rag_memory_count})</span>
                <span>{expandedAgent === agent.department ? '\u25B2' : '\u25BC'}</span>
              </button>
            </div>

            {/* Memory expanded */}
            {expandedAgent === agent.department && (
              <div className="space-y-1 max-h-40 overflow-y-auto">
                <div className="flex items-center gap-2 mb-2">
                  <input
                    type="file"
                    ref={(el) => { fileInputRefs.current[agent.department] = el }}
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) handleUpload(agent.department, file)
                      e.target.value = ''
                    }}
                  />
                  <button
                    onClick={() => fileInputRefs.current[agent.department]?.click()}
                    disabled={uploadingFor === agent.department}
                    className="px-2 py-1 rounded text-xs transition-colors"
                    style={{ background: '#1E2A3A', color: '#f97316' }}
                  >
                    {uploadingFor === agent.department ? 'Uploading...' : '+ Upload Memory'}
                  </button>
                </div>

                {(memoryData[agent.department] || []).length > 0 ? (
                  memoryData[agent.department].map((f) => (
                    <div key={f.filename} className="flex items-center justify-between text-xs py-1">
                      <span className="text-gray-300 truncate flex-1">{f.filename}</span>
                      <span className="mx-2" style={{ color: '#6B7280' }}>
                        {(f.size_bytes / 1024).toFixed(1)}KB
                      </span>
                      <button
                        onClick={() => handleDeleteMemory(agent.department, f.filename)}
                        className="text-red-400 hover:text-red-300 px-1"
                        title="Delete"
                      >
                        &#215;
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs py-2" style={{ color: '#6B7280' }}>No knowledge files</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
