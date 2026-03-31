import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinPayment } from '../../types'

const TYPE_COLOR: Record<string, string> = {
  receipt: '#16a34a',
  payment: '#f97316'
}

export default function Payments() {
  const [payments, setPayments] = useState<FinPayment[]>([])
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [newForm, setNewForm] = useState({ payment_type: 'receipt', payment_date: new Date().toISOString().slice(0,10), currency: 'SGD', amount: '', payment_method: '', reference: '', notes: '', customer_id: '', vendor_id: '' })
  const [creating, setCreating] = useState(false)
  const [customers, setCustomers] = useState<any[]>([])
  const [vendors, setVendors] = useState<any[]>([])
  const [showNewParty, setShowNewParty] = useState(false)
  const [newPartyForm, setNewPartyForm] = useState({ code: '', name: '', email: '', phone: '' })
  const [creatingParty, setCreatingParty] = useState(false)

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
    portalApi.getPayments(entityId)
      .then(r => setPayments(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceCustomers(entityId).then(r => setCustomers(r.data?.data || [])).catch(() => {})
    portalApi.getFinanceVendors(entityId).then(r => setVendors(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Payments</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Payment
          </button>
        </div>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : payments.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No payments found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Payment #', 'Type', 'Date', 'Amount', 'Method', 'Reference'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{p.payment_number}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (TYPE_COLOR[p.payment_type] || '#6B7280') + '22', color: TYPE_COLOR[p.payment_type] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {p.payment_type?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.payment_date}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{p.currency} {p.amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.payment_method || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{p.reference || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {showNewModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151', maxHeight: '85vh', overflowY: 'auto' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Payment</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Payment Type *</div>
                <select value={newForm.payment_type} onChange={e => setNewForm(p => ({ ...p, payment_type: e.target.value }))}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }}>
                  <option value="receipt">Receipt (from customer)</option>
                  <option value="payment">Payment (to vendor)</option>
                </select>
              </div>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>
                  {newForm.payment_type === 'receipt' ? 'Customer' : 'Vendor'}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select
                    value={newForm.payment_type === 'receipt' ? newForm.customer_id : newForm.vendor_id}
                    onChange={e => newForm.payment_type === 'receipt'
                      ? setNewForm(p => ({ ...p, customer_id: e.target.value }))
                      : setNewForm(p => ({ ...p, vendor_id: e.target.value }))}
                    style={{ flex: 1, background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
                    <option value="">— Select —</option>
                    {(newForm.payment_type === 'receipt' ? customers : vendors).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <button onClick={() => setShowNewParty(v => !v)} style={{ background: '#374151', color: '#9CA3AF', border: 'none', borderRadius: 6, padding: '8px 12px', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap' }}>+ New</button>
                </div>
              </div>
              {showNewParty && (
                <div style={{ background: '#111827', borderRadius: 6, padding: 12, border: '1px solid #374151' }}>
                  <div style={{ color: '#9CA3AF', fontSize: 11, marginBottom: 8 }}>
                    Quick-create {newForm.payment_type === 'receipt' ? 'customer' : 'vendor'}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
                    {[['Code *', 'code'], ['Name *', 'name'], ['Email', 'email'], ['Phone', 'phone']].map(([label, key]) => (
                      <div key={key} style={{ flex: '1 1 45%' }}>
                        <div style={{ color: '#6B7280', fontSize: 11, marginBottom: 3 }}>{label}</div>
                        <input value={(newPartyForm as any)[key]} onChange={e => setNewPartyForm(p => ({ ...p, [key]: e.target.value }))}
                          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 4, padding: '6px 8px', fontSize: 12, width: '100%', boxSizing: 'border-box' as const }} />
                      </div>
                    ))}
                  </div>
                  <button onClick={async () => {
                    setCreatingParty(true)
                    try {
                      if (newForm.payment_type === 'receipt') {
                        const r = await portalApi.createFinanceCustomer({ entity_id: entityId, customer_code: newPartyForm.code, name: newPartyForm.name, email: newPartyForm.email, phone: newPartyForm.phone })
                        const created = r.data?.data
                        const list = (await portalApi.getFinanceCustomers(entityId)).data?.data || []
                        setCustomers(list)
                        if (created?.id) setNewForm(p => ({ ...p, customer_id: created.id }))
                      } else {
                        const r = await portalApi.createFinanceVendor({ entity_id: entityId, vendor_code: newPartyForm.code, name: newPartyForm.name, email: newPartyForm.email, phone: newPartyForm.phone })
                        const created = r.data?.data
                        const list = (await portalApi.getFinanceVendors(entityId)).data?.data || []
                        setVendors(list)
                        if (created?.id) setNewForm(p => ({ ...p, vendor_id: created.id }))
                      }
                      setShowNewParty(false)
                      setNewPartyForm({ code: '', name: '', email: '', phone: '' })
                    } catch { } finally { setCreatingParty(false) }
                  }} disabled={creatingParty} style={{ marginTop: 8, background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}>
                    {creatingParty ? 'Creating...' : 'Create & Select'}
                  </button>
                </div>
              )}
              {[
                { label: 'Payment Date *', key: 'payment_date', type: 'date' },
                { label: 'Amount *', key: 'amount', type: 'number' },
                { label: 'Currency', key: 'currency', type: 'text' },
                { label: 'Payment Method', key: 'payment_method', type: 'text' },
                { label: 'Reference', key: 'reference', type: 'text' },
                { label: 'Notes', key: 'notes', type: 'text' },
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
                  await portalApi.createPayment({
                    entity_id: entityId,
                    payment_type: newForm.payment_type,
                    payment_date: newForm.payment_date,
                    currency: newForm.currency,
                    amount: parseFloat(newForm.amount),
                    payment_method: newForm.payment_method || undefined,
                    reference: newForm.reference || undefined,
                    notes: newForm.notes || undefined,
                    customer_id: newForm.payment_type === 'receipt' ? (newForm.customer_id || undefined) : undefined,
                    vendor_id: newForm.payment_type === 'payment' ? (newForm.vendor_id || undefined) : undefined,
                  })
                  setShowNewModal(false)
                  setNewForm({ payment_type: 'receipt', payment_date: new Date().toISOString().slice(0,10), currency: currency, amount: '', payment_method: '', reference: '', notes: '', customer_id: '', vendor_id: '' })
                  setLoading(true)
                  portalApi.getPayments(entityId).then(r => setPayments(r.data?.data || [])).finally(() => setLoading(false))
                } catch { /* ignore */ } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Payment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
