import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinBankAccount } from '../../types'

export default function BankAccounts() {
  const [accounts, setAccounts] = useState<FinBankAccount[]>([])
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [newForm, setNewForm] = useState({ bank_name: '', account_name: '', account_number: '', swift_code: '', currency: 'SGD' })
  const [creating, setCreating] = useState(false)

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

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Bank Accounts</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
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
      {showNewModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Bank Account</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Bank Name *', key: 'bank_name' },
                { label: 'Account Name *', key: 'account_name' },
                { label: 'Account Number', key: 'account_number' },
                { label: 'SWIFT Code', key: 'swift_code' },
                { label: 'Currency *', key: 'currency' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input value={(newForm as any)[f.key]} onChange={e => setNewForm(p => ({ ...p, [f.key]: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewModal(false)} style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  await portalApi.createBankAccount({ entity_id: entityId, ...newForm })
                  setShowNewModal(false)
                  setNewForm({ bank_name: '', account_name: '', account_number: '', swift_code: '', currency: currency })
                  setLoading(true)
                  portalApi.getBankAccounts(entityId).then(r => setAccounts(r.data?.data || [])).finally(() => setLoading(false))
                } catch { /* ignore */ } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Account'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
