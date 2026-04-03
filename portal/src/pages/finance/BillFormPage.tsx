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

type LineItem = { description: string; quantity: string; unit_price: string }

export default function BillFormPage() {
  const navigate = useNavigate()

  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')
  const [vendors, setVendors] = useState<any[]>([])

  const [form, setForm] = useState({
    vendor_id: '',
    bill_date: new Date().toISOString().slice(0, 10),
    due_date: '',
    reference: '',
    tax_amount: '',
    notes: '',
  })
  const [lineItems, setLineItems] = useState<LineItem[]>([{ description: '', quantity: '1', unit_price: '' }])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
  }, [])

  const entityCurrency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceVendors(entityId).then(r => setVendors(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const setLineItem = (idx: number, key: keyof LineItem, val: string) =>
    setLineItems(items => items.map((item, i) => i === idx ? { ...item, [key]: val } : item))

  const addLine = () => setLineItems(items => [...items, { description: '', quantity: '1', unit_price: '' }])
  const removeLine = (idx: number) => setLineItems(items => items.filter((_, i) => i !== idx))

  const subtotal = lineItems.reduce((acc, li) => acc + (parseFloat(li.quantity) || 0) * (parseFloat(li.unit_price) || 0), 0)
  const taxAmt = parseFloat(form.tax_amount) || 0
  const totalAmount = subtotal + taxAmt

  const handleSubmit = async () => {
    setError(null)
    setSaving(true)
    try {
      await portalApi.createBill({
        entity_id: entityId,
        vendor_id: form.vendor_id || undefined,
        bill_date: form.bill_date,
        due_date: form.due_date || undefined,
        reference: form.reference || undefined,
        currency: entityCurrency,
        subtotal,
        tax_amount: taxAmt,
        total_amount: totalAmount,
        notes: form.notes || undefined,
        line_items: lineItems.map(li => ({
          description: li.description,
          quantity: parseFloat(li.quantity) || 1,
          unit_price: parseFloat(li.unit_price) || 0,
          amount: (parseFloat(li.quantity) || 1) * (parseFloat(li.unit_price) || 0),
        })),
      })
      navigate('/mission-control/finance/bills')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create bill')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-sm text-gray-400 hover:text-gray-200 transition-colors">
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>New Bill</h1>
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

        {/* Bill Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Bill Details</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Bill Date" required>
              <input type="date" className={inputClass} style={inputStyle} value={form.bill_date} onChange={set('bill_date')} />
            </FormField>
            <FormField label="Due Date">
              <input type="date" className={inputClass} style={inputStyle} value={form.due_date} onChange={set('due_date')} />
            </FormField>
            <div>
              <label className="block text-xs mb-1" style={{ color: '#9CA3AF' }}>Currency</label>
              <div className="w-full px-3 py-2 rounded-lg text-sm border"
                style={{ background: '#0F172A', borderColor: '#374151', color: '#9CA3AF' }}>
                {entityCurrency}
              </div>
            </div>
            <FormField label="Reference">
              <input className={inputClass} style={inputStyle} value={form.reference} onChange={set('reference')} placeholder="PO-001" />
            </FormField>
          </div>
        </div>

        {/* Vendor */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Vendor</div>
          <FormField label="Vendor">
            <select className={inputClass} style={inputStyle} value={form.vendor_id} onChange={set('vendor_id')}>
              <option value="">— Select vendor —</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </FormField>
        </div>

        {/* Line Items */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Line Items</div>
          <div className="space-y-3">
            {/* Header row */}
            <div className="grid gap-2" style={{ gridTemplateColumns: '1fr 80px 120px 40px' }}>
              <div className="text-xs" style={{ color: '#6B7280' }}>Description</div>
              <div className="text-xs" style={{ color: '#6B7280' }}>Qty</div>
              <div className="text-xs" style={{ color: '#6B7280' }}>Unit Price</div>
              <div />
            </div>
            {lineItems.map((li, idx) => (
              <div key={idx} className="grid gap-2 items-center" style={{ gridTemplateColumns: '1fr 80px 120px 40px' }}>
                <input
                  className={inputClass}
                  style={inputStyle}
                  value={li.description}
                  onChange={e => setLineItem(idx, 'description', e.target.value)}
                  placeholder="Item description"
                />
                <input
                  type="number"
                  className={inputClass}
                  style={inputStyle}
                  value={li.quantity}
                  onChange={e => setLineItem(idx, 'quantity', e.target.value)}
                  min="0"
                />
                <input
                  type="number"
                  className={inputClass}
                  style={inputStyle}
                  value={li.unit_price}
                  onChange={e => setLineItem(idx, 'unit_price', e.target.value)}
                  min="0"
                  placeholder="0.00"
                />
                <button
                  onClick={() => removeLine(idx)}
                  disabled={lineItems.length === 1}
                  className="text-xs rounded"
                  style={{ color: '#6B7280', background: 'transparent', border: 'none', cursor: lineItems.length === 1 ? 'default' : 'pointer', opacity: lineItems.length === 1 ? 0.3 : 1 }}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              onClick={addLine}
              className="text-xs px-3 py-1.5 rounded-lg"
              style={{ background: '#1E2A3A', color: '#9CA3AF', border: '1px solid #374151', cursor: 'pointer' }}
            >
              + Add Line
            </button>
          </div>

          {/* Totals */}
          <div className="mt-4 space-y-2" style={{ maxWidth: 280, marginLeft: 'auto' }}>
            <div className="flex justify-between text-sm">
              <span style={{ color: '#9CA3AF' }}>Subtotal</span>
              <span className="text-white">{entityCurrency} {subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm items-center">
              <span style={{ color: '#9CA3AF' }}>Tax</span>
              <input
                type="number"
                className="px-2 py-1 rounded text-sm text-white border outline-none"
                style={{ background: '#1E2A3A', borderColor: '#374151', width: 120, textAlign: 'right' }}
                value={form.tax_amount}
                onChange={set('tax_amount')}
                placeholder="0.00"
                min="0"
              />
            </div>
            <div className="flex justify-between text-sm font-semibold border-t pt-2" style={{ borderColor: '#374151' }}>
              <span style={{ color: '#9CA3AF' }}>Total</span>
              <span className="text-white">{entityCurrency} {totalAmount.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Notes</div>
          <FormField label="Notes">
            <textarea
              className={`${inputClass} resize-none`}
              style={inputStyle}
              rows={3}
              value={form.notes}
              onChange={set('notes')}
              placeholder="Additional notes..."
            />
          </FormField>
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
          disabled={saving || !entityId}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316', opacity: saving || !entityId ? 0.6 : 1 }}
        >
          {saving ? 'Creating...' : 'Create Bill'}
        </button>
      </div>
    </div>
  )
}
