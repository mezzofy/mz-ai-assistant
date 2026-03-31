import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinExpense } from '../../types'
import { CheckCircle, XCircle } from 'lucide-react'

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
  const [newForm, setNewForm] = useState({ expense_date: new Date().toISOString().slice(0,10), category: '', description: '', vendor_id: '', currency: 'SGD', amount: '', tax_amount: '' })
  const [creating, setCreating] = useState(false)
  const [vendors, setVendors] = useState<any[]>([])
  const [showNewVendor, setShowNewVendor] = useState(false)
  const [newVendorForm, setNewVendorForm] = useState({ vendor_code: '', name: '', email: '', phone: '' })
  const [creatingVendor, setCreatingVendor] = useState(false)
  const [categories, setCategories] = useState<string[]>(['Travel', 'Meals & Entertainment', 'Office Supplies', 'Equipment', 'Software & Subscriptions', 'Marketing', 'Professional Fees', 'Utilities', 'Rent', 'Other'])
  const [showNewCategory, setShowNewCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')

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

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceVendors(entityId).then(r => setVendors(r.data?.data || [])).catch(() => {})
  }, [entityId])

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
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                          <CheckCircle size={11} /> Approve
                        </button>
                        <button onClick={() => handleAction(exp.id, 'reject')}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                          <XCircle size={11} /> Reject
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
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151', maxHeight: '85vh', overflowY: 'auto' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Expense</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Date *</div>
                <input type="date" value={newForm.expense_date} onChange={e => setNewForm(p => ({ ...p, expense_date: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Category *</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={newForm.category} onChange={e => setNewForm(p => ({ ...p, category: e.target.value }))}
                    style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
                    <option value="">— Select category —</option>
                    {categories.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <button onClick={() => setShowNewCategory(v => !v)} style={{ background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 6, padding: '8px 12px', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap' }}>+ New</button>
                </div>
              </div>
              {showNewCategory && (
                <div style={{ background: '#111827', borderRadius: 6, padding: 12, border: '1px solid #374151' }}>
                  <div style={{ color: '#9CA3AF', fontSize: 11, marginBottom: 8 }}>Add custom category</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input value={newCategoryName} onChange={e => setNewCategoryName(e.target.value)} placeholder="Category name"
                      style={{ flex: 1, background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, boxSizing: 'border-box' as const }} />
                    <button onClick={() => {
                      if (!newCategoryName.trim()) return
                      setCategories(prev => [...prev, newCategoryName.trim()])
                      setNewForm(p => ({ ...p, category: newCategoryName.trim() }))
                      setNewCategoryName('')
                      setShowNewCategory(false)
                    }} style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', fontSize: 12 }}>Add & Select</button>
                  </div>
                </div>
              )}
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Description *</div>
                <input value={newForm.description} onChange={e => setNewForm(p => ({ ...p, description: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Vendor</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={newForm.vendor_id} onChange={e => setNewForm(p => ({ ...p, vendor_id: e.target.value }))}
                    style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
                    <option value="">— Select vendor (optional) —</option>
                    {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                  </select>
                  <button onClick={() => setShowNewVendor(v => !v)} style={{ background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 6, padding: '8px 12px', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap' }}>+ New</button>
                </div>
              </div>
              {showNewVendor && (
                <div style={{ background: '#111827', borderRadius: 6, padding: 12, border: '1px solid #374151' }}>
                  <div style={{ color: '#9CA3AF', fontSize: 11, marginBottom: 8 }}>Quick-create vendor</div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
                    {[['Code *', 'vendor_code'], ['Name *', 'name'], ['Email', 'email'], ['Phone', 'phone']].map(([label, key]) => (
                      <div key={key} style={{ flex: '1 1 45%' }}>
                        <div style={{ color: '#6B7280', fontSize: 11, marginBottom: 3 }}>{label}</div>
                        <input value={(newVendorForm as any)[key]} onChange={e => setNewVendorForm(p => ({ ...p, [key]: e.target.value }))}
                          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }} />
                      </div>
                    ))}
                  </div>
                  <button onClick={async () => {
                    setCreatingVendor(true)
                    try {
                      const r = await portalApi.createFinanceVendor({ entity_id: entityId, ...newVendorForm })
                      const created = r.data?.data
                      const list = (await portalApi.getFinanceVendors(entityId)).data?.data || []
                      setVendors(list)
                      if (created?.id) setNewForm(p => ({ ...p, vendor_id: created.id }))
                      setShowNewVendor(false)
                      setNewVendorForm({ vendor_code: '', name: '', email: '', phone: '' })
                    } catch { } finally { setCreatingVendor(false) }
                  }} disabled={creatingVendor} style={{ marginTop: 8, background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                    {creatingVendor ? 'Creating...' : 'Create & Select'}
                  </button>
                </div>
              )}
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Currency</div>
                <input value={newForm.currency} onChange={e => setNewForm(p => ({ ...p, currency: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Amount *</div>
                <input type="number" value={newForm.amount} onChange={e => setNewForm(p => ({ ...p, amount: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Tax Amount</div>
                <input type="number" value={newForm.tax_amount} onChange={e => setNewForm(p => ({ ...p, tax_amount: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewModal(false)} style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  await portalApi.createExpense({
                    entity_id: entityId,
                    expense_date: newForm.expense_date,
                    category: newForm.category,
                    description: newForm.description,
                    vendor_id: newForm.vendor_id || undefined,
                    currency: newForm.currency,
                    amount: parseFloat(newForm.amount) || 0,
                    tax_amount: parseFloat(newForm.tax_amount) || 0,
                  })
                  setShowNewModal(false)
                  setNewForm({ expense_date: new Date().toISOString().slice(0,10), category: '', description: '', vendor_id: '', currency: currency, amount: '', tax_amount: '' })
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
