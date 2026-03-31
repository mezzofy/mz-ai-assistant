import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'

const REPORT_TYPES = [
  { value: 'profit-loss', label: 'Profit & Loss' },
  { value: 'balance-sheet', label: 'Balance Sheet' },
  { value: 'trial-balance', label: 'Trial Balance' },
  { value: 'ar-aging', label: 'AR Aging' },
  { value: 'ap-aging', label: 'AP Aging' },
  { value: 'cash-flow', label: 'Cash Flow' },
  { value: 'tax-summary', label: 'Tax Summary' },
]

export default function Reports() {
  const [reportType, setReportType] = useState('profit-loss')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
    // Default to current month
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    setStartDate(`${y}-${m}-01`)
    setEndDate(`${y}-${m}-${String(new Date(y, now.getMonth() + 1, 0).getDate()).padStart(2, '0')}`)
  }, [])

  const handleGenerate = async () => {
    if (!entityId || !startDate || !endDate) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const r = await portalApi.getFinanceReport(reportType, { entity_id: entityId, start_date: startDate, end_date: endDate })
      setResult(r.data?.data || r.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to generate report')
    } finally {
      setLoading(false)
    }
  }

  const selectStyle = { background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13 }
  const inputStyle = { ...selectStyle, width: 150 }

  return (
    <div style={{ padding: 24, color: '#F9FAFB' }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 20px' }}>Financial Reports</h1>

      {/* Controls */}
      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Report Type</div>
            <select value={reportType} onChange={e => setReportType(e.target.value)} style={{ ...selectStyle, width: 180 }}>
              {REPORT_TYPES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <div>
            <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Entity</div>
            <select value={entityId} onChange={e => setEntityId(e.target.value)} style={{ ...selectStyle, width: 180 }}>
              {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select>
          </div>
          <div>
            <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Start Date</div>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>End Date</div>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={inputStyle} />
          </div>
          <button onClick={handleGenerate} disabled={loading}
            style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 6, padding: '9px 20px', cursor: 'pointer', fontSize: 13, fontWeight: 600, height: 38 }}>
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: '#dc262622', border: '1px solid #dc2626', borderRadius: 6, padding: '12px 16px', color: '#dc2626', marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid #1E3A5F', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
              {REPORT_TYPES.find(r => r.value === reportType)?.label} — {startDate} to {endDate}
            </h3>
          </div>
          <div style={{ padding: 20 }}>
            {Array.isArray(result) ? (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#374151' }}>
                    {Object.keys(result[0] || {}).map(k => (
                      <th key={k} style={{ padding: '8px 12px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500, textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.map((row: any, i: number) => (
                    <tr key={i} style={{ borderTop: '1px solid #374151' }}>
                      {Object.values(row).map((v: any, j: number) => (
                        <td key={j} style={{ padding: '8px 12px', color: '#D1D5DB' }}>{typeof v === 'number' ? v.toLocaleString('en-SG', { minimumFractionDigits: 2 }) : String(v ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <pre style={{ color: '#D1D5DB', fontSize: 12, overflow: 'auto', maxHeight: 500, margin: 0 }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {!result && !loading && !error && (
        <div style={{ padding: 60, textAlign: 'center', color: '#6B7280', background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F' }}>
          Select report parameters and click Generate
        </div>
      )}
    </div>
  )
}
