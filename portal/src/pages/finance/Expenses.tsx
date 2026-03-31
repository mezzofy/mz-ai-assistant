import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinExpense } from '../../types'

const STATUS_TABS = ['All', 'pending', 'approved', 'rejected', 'reimbursed']
const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b', approved: '#16a34a', rejected: '#dc2626', reimbursed: '#3b82f6'
}

export default function Expenses() {
  const [expenses, setExpenses] = useState<FinExpense[]>([])
  const [activeTab, setActiveTab] = useState('All')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [newForm, setNewForm] = useState({ expense_date: new Date().toISOString().slice(0,10), category: '', description: '', vendor_name: '', currency: 'SGD', amount: '', tax_amount: '' })
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
    const status = activeTab === 'All' ? undefined : activeTab
    portalApi.getExpenses(entityId, status)
      .then(r => setExpenses(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    await portalApi.approveExpense(id, action)
    setExpenses(prev => prev.map(e => e.id === id ? { ...e, status: (action === 'approve' ? 'approved' : 'rejected') as FinExpense['status'] } : e))
  }

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Expenses</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Expense
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
        ) : expenses.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No expenses found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Expense #', 'Date', 'Category', 'Description', 'Amount', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {expenses.map(exp => (
                <tr key={exp.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{exp.expense_number}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{exp.expense_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{exp.category}</td>
                  <td style={{ padding: '10px 14px' }}>{exp.description}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{exp.currency} {exp.amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[exp.status] || '#6B7280') + '22', color: STATUS_COLOR[exp.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {exp.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {exp.status === 'pending' && (
                      <>
                        <button onClick={() => handleAction(exp.id, 'approve')}
                          style={{ background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                          Approve
                        </button>
                        <button onClick={() => handleAction(exp.id, 'reject')}
                          style={{ background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                          Reject
                        </button>
                      </>
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
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Expense</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Date *', key: 'expense_date', type: 'date' },
                { label: 'Category *', key: 'category', type: 'text' },
                { label: 'Description *', key: 'description', type: 'text' },
                { label: 'Vendor Name', key: 'vendor_name', type: 'text' },
                { label: 'Currency', key: 'currency', type: 'text' },
                { label: 'Amount *', key: 'amount', type: 'number' },
                { label: 'Tax Amount', key: 'tax_amount', type: 'number' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input type={f.type} value={(newForm as any)[f.key]} onChange={e => setNewForm(p => ({ ...p, [f.key]: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewModal(false)} style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  await portalApi.createExpense({ entity_id: entityId, ...newForm, amount: parseFloat(newForm.amount) || 0, tax_amount: parseFloat(newForm.tax_amount) || 0 })
                  setShowNewModal(false)
                  setNewForm({ expense_date: new Date().toISOString().slice(0,10), category: '', description: '', vendor_name: '', currency: currency, amount: '', tax_amount: '' })
                  setLoading(true)
                  portalApi.getExpenses(entityId, activeTab === 'All' ? undefined : activeTab).then(r => setExpenses(r.data?.data || [])).finally(() => setLoading(false))
                } catch { /* ignore */ } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Expense'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
