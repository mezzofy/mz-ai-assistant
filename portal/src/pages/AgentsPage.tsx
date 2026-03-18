import React, { useState, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { Agent } from '../types'

export default function AgentsPage() {
  const qc = useQueryClient()
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [memoryData, setMemoryData] = useState<Record<string, { filename: string; size_bytes: number }[]>>({})
  const [uploadingFor, setUploadingFor] = useState<string | null>(null)
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
    try {
      await portalApi.uploadAgentMemory(dept, file)
      await refreshMemory(dept)
    } catch {
      // ignore
    } finally {
      setUploadingFor(null)
    }
  }

  const handleDeleteMemory = async (dept: string, filename: string) => {
    try {
      await portalApi.deleteAgentMemory(dept, filename)
      await refreshMemory(dept)
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        Agents
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <div
            key={agent.department}
            className="rounded-xl border p-5"
            style={{ background: '#111827', borderColor: '#1E2A3A' }}
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: agent.is_busy ? '#00D4AA' : '#374151' }}
                  />
                  <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
                </div>
                <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
                  {agent.department}
                </div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold" style={{ color: '#f97316' }}>
                  {agent.tasks_today}
                </div>
                <div className="text-xs" style={{ color: '#6B7280' }}>today</div>
              </div>
            </div>

            <div className="space-y-1 mb-3">
              {agent.skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-block mr-1 mb-1 px-2 py-0.5 rounded text-xs"
                  style={{ background: '#1E2A3A', color: '#9CA3AF' }}
                >
                  {skill}
                </span>
              ))}
            </div>

            <button
              onClick={() => loadMemory(agent.department)}
              className="flex items-center justify-between w-full text-xs py-2 border-t transition-colors hover:text-orange-400"
              style={{ borderColor: '#1E2A3A', color: '#6B7280' }}
            >
              <span>View Memory ({agent.rag_memory_count} docs)</span>
              <span>{expandedAgent === agent.department ? '\u25B2' : '\u25BC'}</span>
            </button>

            {expandedAgent === agent.department && (
              <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                {/* Upload button */}
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
                        x
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
