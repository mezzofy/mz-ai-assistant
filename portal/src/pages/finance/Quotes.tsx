import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinQuote } from '../../types'
import { Send, ArrowRight } from 'lucide-react'

const STATUS_TABS = ['All', 'draft', 'sent', 'accepted', 'declined', 'expired', 'converted']
const STATUS_COLOR: Record<string, string> = {
  draft: '#6B7280',
  sent: '#3b82f6',
  accepted: '#16a34a',
  declined: '#dc2626',
  expired: '#f59e0b',
  converted: '#8b5cf6'
}

export default function Quotes() {
  const [quotes, setQuotes] = useState<FinQuote[]>([])
  const [activeTab, setActiveTab] = useState('All')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [customers, setCustomers] = useState<any[]>([])
  const [newForm, setNewForm] = useState({ customer_id: '', quote_date: new Date().toISOString().slice(0,10), expiry_date: '', currency: 'SGD', notes: '', line_items: [{ description: '', quantity: 1, unit_price: 0 }] })
  const [creating, setCreating] = useState(false)
  const [showNewCustomer, setShowNewCustomer] = useState(false)
  const [newCustomerForm, setNewCustomerForm] = useState({ customer_code: '', name: '', email: '', phone: '' })
  const [creatingCustomer, setCreatingCustomer] = useState(false)

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
    portalApi.getQuotes(entityId)
      .then(r => {
        const data: FinQuote[] = r.data?.data || []
        setQuotes(activeTab === 'All' ? data : data.filter(q => q.status === activeTab))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceCustomers(entityId).then(r => setCustomers(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Quotes</h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Quote
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #374151' }}>
        {STATUS_TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{
              background: 'none', border: 'none',
              borderBottom: activeTab === tab ? '2px solid #f97316' : '2px solid transparent',
              color: activeTab === tab ? '#f97316' : '#9CA3AF',
              padding: '8px 16px', cursor: 'pointer', fontSize: 13,
              fontWeight: activeTab === tab ? 600 : 400, textTransform: 'capitalize'
            }}>
            {tab}
          </button>
        ))}
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : quotes.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No quotes found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Quote #', 'Customer', 'Date', 'Expiry', 'Total', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {quotes.map(q => (
                <tr key={q.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{q.quote_number}</td>
                  <td style={{ padding: '10px 14px' }}>{(q as any).customer_name || q.customer_id}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{q.quote_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{q.expiry_date || '—'}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{q.currency} {q.total_amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      background: (STATUS_COLOR[q.status] || '#6B7280') + '22',
                      color: STATUS_COLOR[q.status] || '#6B7280',
                      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600
                    }}>
                      {q.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {q.status === 'draft' && (
                      <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#3b82f622', color: '#3b82f6', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                        <Send size={11} /> Send
                      </button>
                    )}
                    {q.status === 'accepted' && (
                      <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        <ArrowRight size={11} /> Invoice
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
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 520, border: '1px solid #374151', maxHeight: '85vh', overflowY: 'auto' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Quote</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Customer *</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={newForm.customer_id} onChange={e => setNewForm(p => ({ ...p, customer_id: e.target.value }))}
                    style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
                    <option value="">— Select customer —</option>
                    {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <button onClick={() => setShowNewCustomer(v => !v)} style={{ background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 6, padding: '8px 12px', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap' }}>+ New</button>
                </div>
              </div>
              {showNewCustomer && (
                <div style={{ background: '#111827', borderRadius: 6, padding: 12, border: '1px solid #374151' }}>
                  <div style={{ color: '#9CA3AF', fontSize: 11, marginBottom: 8 }}>Quick-create customer</div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
                    {[['Code *', 'customer_code'], ['Name *', 'name'], ['Email', 'email'], ['Phone', 'phone']].map(([label, key]) => (
                      <div key={key} style={{ flex: '1 1 45%' }}>
                        <div style={{ color: '#6B7280', fontSize: 11, marginBottom: 3 }}>{label}</div>
                        <input value={(newCustomerForm as any)[key]} onChange={e => setNewCustomerForm(p => ({ ...p, [key]: e.target.value }))}
                          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }} />
                      </div>
                    ))}
                  </div>
                  <button onClick={async () => {
                    setCreatingCustomer(true)
                    try {
                      const r = await portalApi.createFinanceCustomer({ entity_id: entityId, ...newCustomerForm })
                      const created = r.data?.data
                      const list = (await portalApi.getFinanceCustomers(entityId)).data?.data || []
                      setCustomers(list)
                      if (created?.id) setNewForm(p => ({ ...p, customer_id: created.id }))
                      setShowNewCustomer(false)
                      setNewCustomerForm({ customer_code: '', name: '', email: '', phone: '' })
                    } catch { } finally { setCreatingCustomer(false) }
                  }} disabled={creatingCustomer} style={{ marginTop: 8, background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                    {creatingCustomer ? 'Creating...' : 'Create & Select'}
                  </button>
                </div>
              )}
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Quote Date *</div>
                  <input type="date" value={newForm.quote_date} onChange={e => setNewForm(p => ({ ...p, quote_date: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Expiry Date *</div>
                  <input type="date" value={newForm.expiry_date} onChange={e => setNewForm(p => ({ ...p, expiry_date: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Currency</div>
                  <input value={newForm.currency} onChange={e => setNewForm(p => ({ ...p, currency: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 8 }}>Line Items</div>
                {newForm.line_items.map((item, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                    <input placeholder="Description" value={item.description} onChange={e => setNewForm(p => ({ ...p, line_items: p.line_items.map((l, j) => j === i ? { ...l, description: e.target.value } : l) }))}
                      style={{ flex: 3, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, boxSizing: 'border-box' as const }} />
                    <input placeholder="Qty" type="number" value={item.quantity} onChange={e => setNewForm(p => ({ ...p, line_items: p.line_items.map((l, j) => j === i ? { ...l, quantity: parseFloat(e.target.value) || 1 } : l) }))}
                      style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, boxSizing: 'border-box' as const }} />
                    <input placeholder="Price" type="number" value={item.unit_price} onChange={e => setNewForm(p => ({ ...p, line_items: p.line_items.map((l, j) => j === i ? { ...l, unit_price: parseFloat(e.target.value) || 0 } : l) }))}
                      style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, boxSizing: 'border-box' as const }} />
                    {newForm.line_items.length > 1 && (
                      <button onClick={() => setNewForm(p => ({ ...p, line_items: p.line_items.filter((_, j) => j !== i) }))}
                        style={{ background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}>✕</button>
                    )}
                  </div>
                ))}
                <button onClick={() => setNewForm(p => ({ ...p, line_items: [...p.line_items, { description: '', quantity: 1, unit_price: 0 }] }))}
                  style={{ background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>+ Add Line</button>
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Notes</div>
                <input value={newForm.notes} onChange={e => setNewForm(p => ({ ...p, notes: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => { setShowNewModal(false); setShowNewCustomer(false) }}
                style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  const subtotal = newForm.line_items.reduce((s, l) => s + l.quantity * l.unit_price, 0)
                  await portalApi.createQuote({ entity_id: entityId, ...newForm, subtotal, total_amount: subtotal })
                  setShowNewModal(false)
                  setNewForm({ customer_id: '', quote_date: new Date().toISOString().slice(0,10), expiry_date: '', currency, notes: '', line_items: [{ description: '', quantity: 1, unit_price: 0 }] })
                  setLoading(true)
                  portalApi.getQuotes(entityId).then(r => {
                    const data: FinQuote[] = r.data?.data || []
                    setQuotes(activeTab === 'All' ? data : data.filter(q => q.status === activeTab))
                  }).finally(() => setLoading(false))
                } catch { } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Quote'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
