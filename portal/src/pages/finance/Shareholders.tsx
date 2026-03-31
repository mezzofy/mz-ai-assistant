import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinShareholder } from '../../types'

export default function Shareholders() {
  const [shareholders, setShareholders] = useState<FinShareholder[]>([])
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
    portalApi.getShareholders(entityId)
      .then(r => setShareholders(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  return (
    <div className="space-y-5" style={{ color: '#F9FAFB', padding: 24 }}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Shareholders</h1>
        <select value={entityId} onChange={e => setEntityId(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : shareholders.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No shareholders found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Name', 'Type', 'Share Class', 'Shares Held', 'Ownership %', 'Effective Date', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shareholders.map(s => (
                <tr key={s.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{s.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', textTransform: 'capitalize' }}>{s.shareholder_type}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{s.share_class}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{s.shares_held?.toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontWeight: 600 }}>
                    {s.ownership_pct != null ? `${s.ownership_pct.toFixed(2)}%` : '—'}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', fontSize: 12 }}>{s.effective_date}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: s.is_active ? '#16a34a22' : '#6B728022', color: s.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {s.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
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
