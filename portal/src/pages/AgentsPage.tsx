import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { Agent } from '../types'

export default function AgentsPage() {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [memoryData, setMemoryData] = useState<Record<string, { filename: string; size_bytes: number }[]>>({})

  const { data } = useQuery({
    queryKey: ['agents'],
    queryFn: () => portalApi.getAgents().then((r) => r.data),
    refetchInterval: 30000,
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
                <div className="text-lg font-bold" style={{ color: '#6C63FF' }}>
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
              className="flex items-center justify-between w-full text-xs py-2 border-t transition-colors hover:text-indigo-400"
              style={{ borderColor: '#1E2A3A', color: '#6B7280' }}
            >
              <span>View Memory ({agent.rag_memory_count} docs)</span>
              <span>{expandedAgent === agent.department ? '▲' : '▼'}</span>
            </button>

            {expandedAgent === agent.department && (
              <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                {(memoryData[agent.department] || []).length > 0 ? (
                  memoryData[agent.department].map((f) => (
                    <div key={f.filename} className="flex justify-between text-xs py-1">
                      <span className="text-gray-300 truncate">{f.filename}</span>
                      <span style={{ color: '#6B7280' }}>
                        {(f.size_bytes / 1024).toFixed(1)}KB
                      </span>
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
