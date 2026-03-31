import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinTaxCode } from '../../types'

export default function TaxCodes() {
  const [taxCodes, setTaxCodes] = useState<FinTaxCode[]>([])
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
    portalApi.getTaxCodes(entityId)
      .then(r => setTaxCodes(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Tax Codes</h1>
          <p className="text-sm" style={{ color: '#6B7280', margin: '4px 0 0' }}>Finance settings — tax configuration</p>
        </div>
        <select value={entityId} onChange={e => setEntityId(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : taxCodes.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No tax codes found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Code', 'Name', 'Type', 'Rate', 'Applies To', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {taxCodes.map(tc => (
                <tr key={tc.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{tc.code}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{tc.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{tc.tax_type}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{tc.rate}%</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{tc.applies_to}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: tc.is_active ? '#16a34a22' : '#6B728022', color: tc.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {tc.is_active ? 'ACTIVE' : 'INACTIVE'}
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
