import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'

interface FinEntity {
  id: string
  name: string
  base_currency: string
}

interface FinAccount {
  id: string
  entity_id: string
  category_id: string | null
  code: string
  name: string
  description: string | null
  currency: string
  account_type: string
  is_bank_account: boolean
  is_control: boolean
  is_active: boolean
}

const ACCOUNT_TYPE_COLORS: Record<string, { bg: string; color: string }> = {
  asset:     { bg: 'rgba(59,130,246,0.15)',  color: '#93C5FD' },
  assets:    { bg: 'rgba(59,130,246,0.15)',  color: '#93C5FD' },
  liability: { bg: 'rgba(239,68,68,0.15)',   color: '#FCA5A5' },
  liabilities: { bg: 'rgba(239,68,68,0.15)', color: '#FCA5A5' },
  equity:    { bg: 'rgba(139,92,246,0.15)',  color: '#C4B5FD' },
  income:    { bg: 'rgba(34,197,94,0.15)',   color: '#86EFAC' },
  revenue:   { bg: 'rgba(34,197,94,0.15)',   color: '#86EFAC' },
  expense:   { bg: 'rgba(249,115,22,0.15)',  color: '#FDBA74' },
  expenses:  { bg: 'rgba(249,115,22,0.15)',  color: '#FDBA74' },
}

function getAccountTypeBadge(accountType: string) {
  const key = accountType.toLowerCase()
  const style = ACCOUNT_TYPE_COLORS[key] ?? { bg: 'rgba(107,114,128,0.15)', color: '#9CA3AF' }
  return style
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

export default function ChartOfAccountsPage() {
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [entityId, setEntityId] = useState<string>('')
  const [accounts, setAccounts] = useState<FinAccount[]>([])
  const [loadingEntities, setLoadingEntities] = useState(true)
  const [loadingAccounts, setLoadingAccounts] = useState(false)

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
    setLoadingAccounts(true)
    portalApi.getFinanceAccounts(entityId)
      .then(r => {
        const data = r.data?.data ?? r.data ?? []
        setAccounts(Array.isArray(data) ? data : [])
      })
      .catch(() => setAccounts([]))
      .finally(() => setLoadingAccounts(false))
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
            Chart of Accounts
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            View accounts by entity
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
        {loadingEntities || loadingAccounts ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            Loading...
          </div>
        ) : accounts.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            {entityId ? 'No accounts found for this entity.' : 'Select an entity to view accounts.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1F2937', borderBottom: '1px solid #1E2A3A' }}>
                  {['Code', 'Name', 'Account Type', 'Currency', 'Bank Acct', 'Active'].map(col => (
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
                {accounts.map((acct, idx) => {
                  const badge = getAccountTypeBadge(acct.account_type)
                  return (
                    <tr
                      key={acct.id}
                      style={{
                        borderBottom: '1px solid #1E2A3A',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.05)')}
                      onMouseLeave={e => (e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)')}
                    >
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                        {acct.code}
                      </td>
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13 }}>
                        {acct.name}
                        {acct.description && (
                          <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>{acct.description}</div>
                        )}
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
                            background: badge.bg,
                            color: badge.color,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {acct.account_type}
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', color: '#9CA3AF', fontSize: 13 }}>
                        {acct.currency}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {acct.is_bank_account ? (
                          <span style={{ color: '#86EFAC' }}>Yes</span>
                        ) : (
                          <span style={{ color: '#4B5563' }}>No</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {acct.is_active ? (
                          <span style={{ color: '#86EFAC' }}>Active</span>
                        ) : (
                          <span style={{ color: '#6B7280' }}>Inactive</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
