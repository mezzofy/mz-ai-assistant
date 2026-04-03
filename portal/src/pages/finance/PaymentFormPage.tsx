import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'

const inputClass = 'w-full px-3 py-2 rounded-lg text-sm text-white border outline-none'
const inputStyle = { background: '#1E2A3A', borderColor: '#374151' }

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: '#9CA3AF' }}>
        {label} {required && <span style={{ color: '#f97316' }}>*</span>}
      </label>
      {children}
    </div>
  )
}

export default function PaymentFormPage() {
  const navigate = useNavigate()

  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')
  const [customers, setCustomers] = useState<any[]>([])
  const [vendors, setVendors] = useState<any[]>([])

  const [form, setForm] = useState({
    payment_type: 'receipt',
    payment_date: new Date().toISOString().slice(0, 10),
    currency: 'SGD',
    amount: '',
    payment_method: '',
    reference: '',
    notes: '',
    customer_id: '',
    vendor_id: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceCustomers(entityId).then(r => setCustomers(r.data?.data || [])).catch(() => {})
    portalApi.getFinanceVendors(entityId).then(r => setVendors(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async () => {
    setError(null)
    setSaving(true)
    try {
      await portalApi.createPayment({
        entity_id: entityId,
        payment_type: form.payment_type,
        payment_date: form.payment_date,
        currency: form.currency,
        amount: parseFloat(form.amount) || 0,
        payment_method: form.payment_method || undefined,
        reference: form.reference || undefined,
        notes: form.notes || undefined,
        customer_id: form.payment_type === 'receipt' ? (form.customer_id || undefined) : undefined,
        vendor_id: form.payment_type === 'payment' ? (form.vendor_id || undefined) : undefined,
      })
      navigate('/mission-control/finance/payments')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create payment')
    } finally {
      setSaving(false)
    }
  }

  const isReceipt = form.payment_type === 'receipt'

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-sm text-gray-400 hover:text-gray-200 transition-colors">
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>New Payment</h1>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      <div className="rounded-xl border p-6 space-y-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        {/* Entity */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Entity</div>
          <FormField label="Entity" required>
            <select className={inputClass} style={inputStyle} value={entityId} onChange={e => setEntityId(e.target.value)}>
              {entities.map(ent => <option key={ent.id} value={ent.id}>{ent.name}</option>)}
            </select>
          </FormField>
        </div>

        {/* Payment Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Payment Details</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Payment Type" required>
              <select className={inputClass} style={inputStyle} value={form.payment_type} onChange={set('payment_type')}>
                <option value="receipt">Receipt (from customer)</option>
                <option value="payment">Payment (to vendor)</option>
              </select>
            </FormField>
            <FormField label="Payment Date" required>
              <input type="date" className={inputClass} style={inputStyle} value={form.payment_date} onChange={set('payment_date')} />
            </FormField>
            <FormField label="Amount" required>
              <input type="number" className={inputClass} style={inputStyle} value={form.amount} onChange={set('amount')} placeholder="0.00" min="0" />
            </FormField>
            <FormField label="Currency">
              <input className={inputClass} style={inputStyle} value={form.currency} onChange={set('currency')} placeholder="SGD" />
            </FormField>
            <FormField label="Payment Method">
              <input className={inputClass} style={inputStyle} value={form.payment_method} onChange={set('payment_method')} placeholder="Bank Transfer, Cash, Cheque..." />
            </FormField>
            <FormField label="Reference">
              <input className={inputClass} style={inputStyle} value={form.reference} onChange={set('reference')} placeholder="REF-001" />
            </FormField>
          </div>
        </div>

        {/* Account Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Account Info</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {isReceipt ? (
              <FormField label="Customer">
                <select className={inputClass} style={inputStyle} value={form.customer_id} onChange={set('customer_id')}>
                  <option value="">— Select customer —</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </FormField>
            ) : (
              <FormField label="Vendor">
                <select className={inputClass} style={inputStyle} value={form.vendor_id} onChange={set('vendor_id')}>
                  <option value="">— Select vendor —</option>
                  {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </FormField>
            )}
            <FormField label="Notes">
              <input className={inputClass} style={inputStyle} value={form.notes} onChange={set('notes')} placeholder="Additional notes..." />
            </FormField>
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex justify-end gap-3 pb-6">
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving || !entityId || !form.amount}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316', opacity: saving || !entityId || !form.amount ? 0.6 : 1 }}
        >
          {saving ? 'Creating...' : 'Create Payment'}
        </button>
      </div>
    </div>
  )
}
