import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { JournalEntry } from '../../types'
import { CheckCircle, RotateCcw } from 'lucide-react'

const STATUS_TABS = ['All', 'draft', 'posted', 'reversed']
const STATUS_COLOR: Record<string, string> = {
  draft: '#6B7280', posted: '#16a34a', reversed: '#dc2626'
}

export default function JournalEntries() {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [activeTab, setActiveTab] = useState('All')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [newForm, setNewForm] = useState({ description: '', entry_date: new Date().toISOString().slice(0,10), reference: '', currency: 'SGD' })
  const [lines, setLines] = useState([{ account_id: '', description: '', debit_amount: '', credit_amount: '' }, { account_id: '', description: '', debit_amount: '', credit_amount: '' }])
  const [creating, setCreating] = useState(false)
  const [accounts, setAccounts] = useState<any[]>([])
  const [showNewAccount, setShowNewAccount] = useState(false)
  const [newAccountForm, setNewAccountForm] = useState({ code: '', name: '', account_type: 'expense', currency: 'SGD' })
  const [creatingAccount, setCreatingAccount] = useState(false)

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
    const status = activeTab === 'All' ? undefined : activeTab
    portalApi.getJournalEntries(entityId, status)
      .then(r => setEntries(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceAccounts(entityId).then(r => setAccounts(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const handlePost = async (id: string) => {
    await portalApi.postJournalEntry(id)
    setEntries(prev => prev.map(e => e.id === id ? { ...e, status: 'posted' as const } : e))
  }

  const handleReverse = async (id: string) => {
    if (!confirm('Reverse this journal entry?')) return
    await portalApi.reverseJournalEntry(id)
    setEntries(prev => prev.map(e => e.id === id ? { ...e, status: 'reversed' as const } : e))
  }

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Journal Entries</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Entry
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #374151' }}>
        {STATUS_TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{ background: 'none', border: 'none', borderBottom: activeTab === tab ? '2px solid #f97316' : '2px solid transparent', color: activeTab === tab ? '#f97316' : '#9CA3AF', padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: activeTab === tab ? 600 : 400, textTransform: 'capitalize' }}>
            {tab}
          </button>
        ))}
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : entries.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No journal entries found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Entry #', 'Date', 'Description', 'Currency', 'Reference', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(je => (
                <tr key={je.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{je.entry_number}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{je.entry_date}</td>
                  <td style={{ padding: '10px 14px' }}>{je.description}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{je.currency}</td>
                  <td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{je.reference || '—'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[je.status] || '#6B7280') + '22', color: STATUS_COLOR[je.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {je.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {je.status === 'draft' && (
                      <button onClick={() => handlePost(je.id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                        <CheckCircle size={11} /> Post
                      </button>
                    )}
                    {je.status === 'posted' && (
                      <button onClick={() => handleReverse(je.id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        <RotateCcw size={11} /> Reverse
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {showNewModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 600, border: '1px solid #374151', maxHeight: '80vh', overflowY: 'auto' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Journal Entry</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 2 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Description *</div>
                  <input value={newForm.description} onChange={e => setNewForm(p => ({ ...p, description: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Date *</div>
                  <input type="date" value={newForm.entry_date} onChange={e => setNewForm(p => ({ ...p, entry_date: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 2 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Reference</div>
                  <input value={newForm.reference} onChange={e => setNewForm(p => ({ ...p, reference: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Currency</div>
                  <input value={newForm.currency} onChange={e => setNewForm(p => ({ ...p, currency: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 8 }}>Journal Lines (min 2)</div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#374151' }}>
                      {['Account', 'Description', 'Debit', 'Credit', ''].map(h => (
                        <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((line, i) => (
                      <tr key={i}>
                        <td style={{ padding: '4px 4px' }}>
                          <select value={line.account_id} onChange={e => setLines(prev => prev.map((l, j) => j === i ? { ...l, account_id: e.target.value } : l))}
                            style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '5px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }}>
                            <option value="">— Account —</option>
                            {accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                          </select>
                        </td>
                        {(['description', 'debit_amount', 'credit_amount'] as const).map(field => (
                          <td key={field} style={{ padding: '4px 4px' }}>
                            <input value={(line as any)[field]} onChange={e => setLines(prev => prev.map((l, j) => j === i ? { ...l, [field]: e.target.value } : l))}
                              style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '5px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }} />
                          </td>
                        ))}
                        <td style={{ padding: '4px 4px' }}>
                          {lines.length > 2 && (
                            <button onClick={() => setLines(prev => prev.filter((_, j) => j !== i))}
                              style={{ background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}>✕</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button onClick={() => setLines(prev => [...prev, { account_id: '', description: '', debit_amount: '', credit_amount: '' }])}
                  style={{ marginTop: 8, background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                  + Add Line
                </button>
                <button onClick={() => setShowNewAccount(v => !v)}
                  style={{ marginLeft: 8, background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                  + New Account
                </button>
                {showNewAccount && (
                  <div style={{ background: '#111827', borderRadius: 6, padding: 12, border: '1px solid #374151', marginTop: 8 }}>
                    <div style={{ color: '#9CA3AF', fontSize: 11, marginBottom: 8 }}>Quick-create GL account</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
                      {[['Code *', 'code'], ['Name *', 'name'], ['Currency', 'currency']].map(([label, key]) => (
                        <div key={key} style={{ flex: '1 1 30%' }}>
                          <div style={{ color: '#6B7280', fontSize: 11, marginBottom: 3 }}>{label}</div>
                          <input value={(newAccountForm as any)[key]} onChange={e => setNewAccountForm(p => ({ ...p, [key]: e.target.value }))}
                            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }} />
                        </div>
                      ))}
                      <div style={{ flex: '1 1 30%' }}>
                        <div style={{ color: '#6B7280', fontSize: 11, marginBottom: 3 }}>Type</div>
                        <select value={newAccountForm.account_type} onChange={e => setNewAccountForm(p => ({ ...p, account_type: e.target.value }))}
                          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }}>
                          {['asset', 'liability', 'equity', 'revenue', 'expense'].map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </div>
                    </div>
                    <button onClick={async () => {
                      setCreatingAccount(true)
                      try {
                        await portalApi.createFinanceAccount({ entity_id: entityId, ...newAccountForm })
                        const r = await portalApi.getFinanceAccounts(entityId)
                        setAccounts(r.data?.data || [])
                        setShowNewAccount(false)
                        setNewAccountForm({ code: '', name: '', account_type: 'expense', currency: 'SGD' })
                      } catch { } finally { setCreatingAccount(false) }
                    }} disabled={creatingAccount} style={{ marginTop: 8, background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                      {creatingAccount ? 'Creating...' : 'Create & Add'}
                    </button>
                  </div>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => { setShowNewModal(false); setLines([{ account_id: '', description: '', debit_amount: '', credit_amount: '' }, { account_id: '', description: '', debit_amount: '', credit_amount: '' }]) }}
                style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  await portalApi.createJournalEntry({
                    entity_id: entityId,
                    entry_date: newForm.entry_date,
                    description: newForm.description,
                    reference: newForm.reference || undefined,
                    currency: newForm.currency,
                    lines: lines.map(l => ({ account_id: l.account_id, description: l.description, debit_amount: parseFloat(l.debit_amount) || 0, credit_amount: parseFloat(l.credit_amount) || 0 }))
                  })
                  setShowNewModal(false)
                  setNewForm({ description: '', entry_date: new Date().toISOString().slice(0,10), reference: '', currency: currency })
                  setLines([{ account_id: '', description: '', debit_amount: '', credit_amount: '' }, { account_id: '', description: '', debit_amount: '', credit_amount: '' }])
                  // Reload
                  setLoading(true)
                  portalApi.getJournalEntries(entityId, activeTab === 'All' ? undefined : activeTab).then(r => setEntries(r.data?.data || [])).finally(() => setLoading(false))
                } catch { /* ignore */ } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Entry'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
