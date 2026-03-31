import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinPeriod } from '../../types'

const STATUS_COLOR: Record<string, string> = {
  open: '#16a34a', closed: '#f59e0b', locked: '#dc2626'
}

export default function Periods() {
  const [periods, setPeriods] = useState<FinPeriod[]>([])
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!entityId) return
    setLoading(true)
    portalApi.getFinancePeriods(entityId)
      .then(r => setPeriods(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  const handleClose = async (id: string) => {
    if (!confirm('Close this period? This cannot be undone.')) return
    await portalApi.closeFinancePeriod(id)
    setPeriods(prev => prev.map(p => p.id === id ? { ...p, status: 'closed' as const } : p))
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Accounting Periods</h1>
          <p className="text-sm" style={{ color: '#6B7280', margin: '4px 0 0' }}>Finance settings — period management</p>
        </div>
        <select value={entityId} onChange={e => setEntityId(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : periods.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No periods found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Name', 'Type', 'Start Date', 'End Date', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periods.map(p => (
                <tr key={p.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{p.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', textTransform: 'capitalize' }}>{p.period_type}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.start_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.end_date}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[p.status] || '#6B7280') + '22', color: STATUS_COLOR[p.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {p.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {p.status === 'open' && (
                      <button onClick={() => handleClose(p.id)}
                        style={{ background: '#f59e0b22', color: '#f59e0b', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        Close Period
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
