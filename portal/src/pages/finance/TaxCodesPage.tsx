import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'

interface FinEntity {
  id: string
  name: string
}

interface TaxCode {
  id: string
  entity_id: string
  code: string
  name: string
  tax_type: string
  rate: number
  applies_to: string | null
  is_active: boolean
}

const selectStyle: React.CSSProperties = {
  background: '#1E2A3A',
  border: '1px solid #374151',
  color: '#F9FAFB',
  borderRadius: 6,
  padding: '8px 12px',
  fontSize: 13,
  minWidth: 220,
  outline: 'none',
}

export default function TaxCodesPage() {
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [entityId, setEntityId] = useState<string>('')
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([])
  const [loadingEntities, setLoadingEntities] = useState(true)
  const [loadingTaxCodes, setLoadingTaxCodes] = useState(false)

  useEffect(() => {
    setLoadingEntities(true)
    portalApi.getFinanceEntities()
      .then(r => {
        const ents: FinEntity[] = r.data?.data || []
        setEntities(ents)
        if (ents.length > 0) setEntityId(ents[0].id)
      })
      .catch(() => {})
      .finally(() => setLoadingEntities(false))
  }, [])

  useEffect(() => {
    if (!entityId) return
    setLoadingTaxCodes(true)
    portalApi.getTaxCodes(entityId)
      .then(r => {
        const data = r.data?.data ?? r.data ?? []
        setTaxCodes(Array.isArray(data) ? data : [])
      })
      .catch(() => setTaxCodes([]))
      .finally(() => setLoadingTaxCodes(false))
  }, [entityId])

  return (
    <div className="space-y-5" style={{ minHeight: '100%' }}>
      {/* Page Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1
            className="text-2xl font-bold text-white"
            style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}
          >
            Tax Codes
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            View tax codes by entity
          </p>
        </div>

        {/* Entity Selector */}
        {!loadingEntities && entities.length > 0 && (
          <div className="flex items-center gap-2">
            <label className="text-xs" style={{ color: '#9CA3AF' }}>Entity</label>
            <select
              value={entityId}
              onChange={e => setEntityId(e.target.value)}
              style={selectStyle}
            >
              {entities.map(ent => (
                <option key={ent.id} value={ent.id}>{ent.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Table Card */}
      <div
        style={{
          background: '#111827',
          border: '1px solid #1E2A3A',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {loadingEntities || loadingTaxCodes ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            Loading...
          </div>
        ) : taxCodes.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            {entityId ? 'No tax codes found for this entity.' : 'Select an entity to view tax codes.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1F2937', borderBottom: '1px solid #1E2A3A' }}>
                  {['Code', 'Name', 'Tax Type', 'Rate (%)', 'Applies To', 'Active'].map(col => (
                    <th
                      key={col}
                      style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: '#4B5563',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {taxCodes.map((tc, idx) => (
                  <tr
                    key={tc.id}
                    style={{
                      borderBottom: '1px solid #1E2A3A',
                      background: idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.05)')}
                    onMouseLeave={e => (e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)')}
                  >
                    <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                      {tc.code}
                    </td>
                    <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13 }}>
                      {tc.name}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 10px',
                          borderRadius: 12,
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'capitalize',
                          background: 'rgba(249,115,22,0.12)',
                          color: '#FDBA74',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {tc.tax_type}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13 }}>
                      {typeof tc.rate === 'number' ? tc.rate.toFixed(2) : tc.rate}%
                    </td>
                    <td style={{ padding: '10px 16px', color: '#9CA3AF', fontSize: 13 }}>
                      {tc.applies_to ?? <span style={{ color: '#4B5563' }}>—</span>}
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 13 }}>
                      {tc.is_active ? (
                        <span style={{ color: '#86EFAC' }}>Active</span>
                      ) : (
                        <span style={{ color: '#6B7280' }}>Inactive</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
