import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import AgentOffice from '../components/AgentOffice'
import type { Session, LlmModel, SystemVitals, AgentStatus } from '../types'

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full mr-2"
      style={{ background: ok ? '#00D4AA' : '#EF4444' }}
    />
  )
}

function FuelGauge({ model }: { model: LlmModel }) {
  const pct = Math.min(model.budget_pct, 100)
  const color = pct >= 95 ? '#EF4444' : pct >= 80 ? '#F59E0B' : '#00D4AA'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-300 font-mono">{model.model}</span>
        <span style={{ color }}>
          ${model.today_cost_usd.toFixed(3)} / ${model.daily_budget_usd}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: '#1E2A3A' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="flex justify-between text-xs" style={{ color: '#6B7280' }}>
        <span>{model.total_tokens.toLocaleString()} tokens</span>
        <span>{model.request_count} reqs</span>
      </div>
    </div>
  )
}

function RadialGauge({ value, label, color }: { value: number; label: string; color: string }) {
  const r = 36
  const circ = 2 * Math.PI * r
  const dash = circ * (value / 100)

  return (
    <div className="flex flex-col items-center">
      <svg width="90" height="90" className="-rotate-90">
        <circle cx="45" cy="45" r={r} fill="none" stroke="#1E2A3A" strokeWidth="6" />
        <circle
          cx="45" cy="45" r={r} fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="text-center -mt-16 mb-10">
        <div className="text-2xl font-bold text-white">{value.toFixed(0)}%</div>
        <div className="text-xs" style={{ color: '#6B7280' }}>{label}</div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [llmPeriod, setLlmPeriod] = useState<'today' | 'week' | 'month'>('today')

  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => portalApi.getSessions().then((r) => r.data),
    refetchInterval: 30000,
  })

  const { data: llmUsage } = useQuery({
    queryKey: ['llm-usage', llmPeriod],
    queryFn: () => portalApi.getLlmUsage(llmPeriod).then((r) => r.data),
    refetchInterval: 60000,
  })

  const { data: vitals } = useQuery({
    queryKey: ['system-vitals'],
    queryFn: () => portalApi.getSystemVitals().then((r) => r.data as SystemVitals),
    refetchInterval: 15000,
  })

  const { data: agentStatusData } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => portalApi.getAgentStatus().then((r) => r.data),
    refetchInterval: 20000,
  })

  const agentList: AgentStatus[] = agentStatusData?.agents || []
  const modelList: LlmModel[] = llmUsage?.models || []
  const sessionList: Session[] = sessions?.sessions || []

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        Mission Control
      </h1>

      {/* Row 1: Sessions + LLM Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Session Monitor */}
        <div className="lg:col-span-2 rounded-xl border p-5" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Active Sessions</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ color: '#6B7280' }}>
                  <th className="text-left pb-2">User</th>
                  <th className="text-left pb-2">Dept</th>
                  <th className="text-left pb-2">Agent</th>
                  <th className="text-left pb-2">Messages</th>
                  <th className="text-left pb-2">Last Active</th>
                  <th className="text-left pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {sessionList.slice(0, 10).map((s) => (
                  <tr key={s.session_id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
                    <td className="py-2 text-gray-200">{s.user_name}</td>
                    <td className="py-2" style={{ color: '#6B7280' }}>{s.department}</td>
                    <td className="py-2" style={{ color: '#6B7280' }}>{s.agent || '—'}</td>
                    <td className="py-2 text-gray-300">{s.message_count}</td>
                    <td className="py-2" style={{ color: '#6B7280' }}>
                      {s.last_active ? new Date(s.last_active).toLocaleTimeString() : '—'}
                    </td>
                    <td className="py-2">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs"
                        style={{
                          background: s.is_active ? 'rgba(0, 212, 170, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                          color: s.is_active ? '#00D4AA' : '#6B7280',
                        }}
                      >
                        {s.is_active ? 'Active' : 'Idle'}
                      </span>
                    </td>
                  </tr>
                ))}
                {sessionList.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center" style={{ color: '#6B7280' }}>
                      No sessions
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* LLM Fuel Gauges */}
        <div className="rounded-xl border p-5" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-300">LLM Budget</h2>
            <div className="flex gap-1">
              {(['today', 'week', 'month'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setLlmPeriod(p)}
                  className="px-2 py-0.5 rounded text-xs transition-all"
                  style={{
                    background: llmPeriod === p ? '#6C63FF' : '#1E2A3A',
                    color: llmPeriod === p ? 'white' : '#6B7280',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-4">
            {modelList.length > 0 ? (
              modelList.map((m) => <FuelGauge key={m.model} model={m} />)
            ) : (
              <p className="text-xs text-center py-8" style={{ color: '#6B7280' }}>No usage data</p>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: System Vitals */}
      {vitals && (
        <div className="rounded-xl border p-5" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <h2 className="text-sm font-semibold text-gray-300 mb-4">System Vitals</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <RadialGauge
              value={vitals.cpu.percent}
              label={`CPU  ·  Load ${vitals.cpu.load_avg_1m.toFixed(2)}`}
              color={vitals.cpu.percent > 80 ? '#EF4444' : '#6C63FF'}
            />
            <div>
              <div className="text-xs text-gray-400 mb-2">Memory</div>
              <div className="text-xl font-bold text-white mb-1">{vitals.memory.percent.toFixed(1)}%</div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: '#1E2A3A' }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${vitals.memory.percent}%`,
                    background: vitals.memory.percent > 80 ? '#EF4444' : '#00D4AA',
                  }}
                />
              </div>
              <div className="text-xs mt-1" style={{ color: '#6B7280' }}>
                {vitals.memory.used_gb.toFixed(1)} / {vitals.memory.total_gb.toFixed(1)} GB
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-2">Disk</div>
              <div className="text-xl font-bold text-white mb-1">{vitals.disk.percent}%</div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: '#1E2A3A' }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${vitals.disk.percent}%`,
                    background: vitals.disk.percent > 80 ? '#EF4444' : '#F59E0B',
                  }}
                />
              </div>
              <div className="text-xs mt-1" style={{ color: '#6B7280' }}>
                {vitals.disk.used_gb.toFixed(0)} / {vitals.disk.total_gb.toFixed(0)} GB
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-3">Services</div>
              <div className="space-y-1.5">
                {([
                  ['FastAPI', vitals.services.fastapi],
                  ['PostgreSQL', vitals.services.postgresql],
                  ['Redis', vitals.services.redis],
                  [`Celery (${vitals.services.celery_workers}w)`, vitals.services.celery_workers > 0],
                  ['Celery Beat', vitals.services.celery_beat],
                ] as [string, boolean][]).map(([name, ok]) => (
                  <div key={name} className="flex items-center text-xs">
                    <StatusDot ok={ok} />
                    <span className="text-gray-300">{name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Row 3: Agent Office Pixel Art */}
      <div className="rounded-xl border p-5" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <h2 className="text-sm font-semibold text-gray-300 mb-4">
          Agent Office
          <span className="ml-2 text-xs font-normal" style={{ color: '#6B7280' }}>
            {agentList.filter((a) => a.is_busy).length} active
          </span>
        </h2>
        <AgentOffice agents={agentList} />
      </div>
    </div>
  )
}
