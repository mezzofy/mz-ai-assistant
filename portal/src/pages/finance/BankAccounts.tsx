import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { FinBankAccount } from '../../types'

export default function BankAccounts() {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<FinBankAccount[]>([])
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
    portalApi.getBankAccounts(entityId)
      .then(r => setAccounts(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Bank Accounts</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => navigate('/mission-control/finance/bank-accounts/new')}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Account
          </button>
        </div>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : accounts.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No bank accounts found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Bank', 'Account Name', 'Account #', 'Currency', 'Balance', 'Last Reconciled', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {accounts.map(a => (
                <tr key={a.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{a.bank_name}</td>
                  <td style={{ padding: '10px 14px' }}>{a.account_name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', fontFamily: 'monospace', fontSize: 12 }}>{a.account_number || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{a.currency}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: a.current_balance >= 0 ? '#16a34a' : '#dc2626' }}>
                    {a.currency} {a.current_balance?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', fontSize: 12 }}>{a.last_reconciled || '—'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: a.is_active ? '#16a34a22' : '#6B728022', color: a.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {a.is_active ? 'ACTIVE' : 'INACTIVE'}
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
