import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { portalApi } from '../../api/portal'

type LineItem = {
  description: string
  quantity: number
  unit_price: number
}

type FormData = {
  customer_id: string
  quote_date: string
  expiry_date: string
  currency: string
  notes: string
  line_items: LineItem[]
}

const EMPTY_FORM: FormData = {
  customer_id: '',
  quote_date: new Date().toISOString().slice(0, 10),
  expiry_date: '',
  currency: 'SGD',
  notes: '',
  line_items: [{ description: '', quantity: 1, unit_price: 0 }],
}

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

const inputClass = 'w-full px-3 py-2 rounded-lg text-sm text-white border outline-none'
const inputStyle = { background: '#1E2A3A', borderColor: '#374151' }

export default function SalesQuoteFormPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [customers, setCustomers] = useState<any[]>([])
  const [showNewCustomer, setShowNewCustomer] = useState(false)
  const [newCustomerForm, setNewCustomerForm] = useState({ customer_code: '', name: '', email: '', phone: '' })
  const [creatingCustomer, setCreatingCustomer] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(isEdit)

  useEffect(() => {
    portalApi.getFinanceEntities().then((r) => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) {
        setEntityId(ents[0].id)
        if (!isEdit) {
          const baseCurrency = ents[0].base_currency || 'SGD'
          setForm((f) => ({ ...f, currency: baseCurrency }))
        }
      }
    }).catch(() => {})
  }, [isEdit])

  useEffect(() => {
    if (!entityId) return
    portalApi.getFinanceCustomers(entityId).then((r) => setCustomers(r.data?.data || [])).catch(() => {})
    if (!isEdit) {
      const ent = entities.find((e) => e.id === entityId)
      if (ent?.base_currency) setForm((f) => ({ ...f, currency: ent.base_currency }))
    }
  }, [entityId, isEdit])

  // Load existing quote in edit mode — runs after entityId is set
  useEffect(() => {
    if (!isEdit || !entityId || !id) return
    setLoading(true)
    portalApi.getQuotes(entityId)
      .then((r) => {
        const quotes = r.data?.data || []
        const quote = quotes.find((q: any) => q.id === id)
        if (quote) {
          setForm({
            customer_id: quote.customer_id || '',
            quote_date: quote.quote_date || new Date().toISOString().slice(0, 10),
            expiry_date: quote.expiry_date || '',
            currency: quote.currency || 'SGD',
            notes: quote.notes || '',
            line_items: (quote.line_items && quote.line_items.length > 0)
              ? quote.line_items.map((li: any) => ({
                  description: li.description || '',
                  quantity: li.quantity ?? 1,
                  unit_price: li.unit_price ?? 0,
                }))
              : [{ description: '', quantity: 1, unit_price: 0 }],
          })
        } else {
          setError('Quote not found')
        }
      })
      .catch(() => setError('Failed to load quote'))
      .finally(() => setLoading(false))
  }, [entityId, id, isEdit])

  async function handleCreateCustomer() {
    setCreatingCustomer(true)
    try {
      const r = await portalApi.createFinanceCustomer({ entity_id: entityId, ...newCustomerForm })
      const created = r.data?.data
      const list = (await portalApi.getFinanceCustomers(entityId)).data?.data || []
      setCustomers(list)
      if (created?.id) setForm((f) => ({ ...f, customer_id: created.id }))
      setShowNewCustomer(false)
      setNewCustomerForm({ customer_code: '', name: '', email: '', phone: '' })
    } catch {
      // silently fail
    } finally {
      setCreatingCustomer(false)
    }
  }

  function updateLineItem(index: number, key: keyof LineItem, value: string | number) {
    setForm((f) => ({
      ...f,
      line_items: f.line_items.map((item, i) => i === index ? { ...item, [key]: value } : item),
    }))
  }

  function addLineItem() {
    setForm((f) => ({ ...f, line_items: [...f.line_items, { description: '', quantity: 1, unit_price: 0 }] }))
  }

  function removeLineItem(index: number) {
    setForm((f) => ({ ...f, line_items: f.line_items.filter((_, i) => i !== index) }))
  }

  async function handleSubmit() {
    setSaving(true)
    setError(null)
    try {
      const subtotal = form.line_items.reduce((s, l) => s + l.quantity * l.unit_price, 0)
      if (isEdit) {
        await portalApi.updateQuote(id!, { entity_id: entityId, ...form, subtotal, total_amount: subtotal })
        navigate('/mission-control/sales/quotes')
      } else {
        await portalApi.createQuote({ entity_id: entityId, ...form, subtotal, total_amount: subtotal })
        navigate('/mission-control/sales/quotes')
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || (isEdit ? 'Failed to update quote' : 'Failed to create quote'))
    } finally {
      setSaving(false)
    }
  }

  const subtotal = form.line_items.reduce((s, l) => s + l.quantity * l.unit_price, 0)

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/mission-control/sales/quotes')}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          {isEdit ? 'Edit Quote' : 'New Quote'}
        </h1>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      <div className="rounded-xl border p-6 space-y-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        {/* Entity Picker */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Finance Entity
          </div>
          <FormField label="Entity" required>
            <select className={inputClass} style={inputStyle} value={entityId} onChange={(e) => setEntityId(e.target.value)}>
              {entities.map((ent) => (
                <option key={ent.id} value={ent.id}>{ent.name}</option>
              ))}
            </select>
          </FormField>
        </div>

        {/* Customer */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Customer
          </div>
          <div className="flex gap-2 mb-3">
            <select
              className={inputClass}
              style={inputStyle}
              value={form.customer_id}
              onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
            >
              <option value="">— Select customer —</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {!isEdit && (
              <button
                onClick={() => setShowNewCustomer((v) => !v)}
                className="px-3 py-2 rounded-lg text-sm whitespace-nowrap"
                style={{ background: '#1E2A3A', color: '#9CA3AF', border: '1px solid #374151' }}
              >
                + New
              </button>
            )}
          </div>

          {showNewCustomer && !isEdit && (
            <div className="rounded-lg p-4 border" style={{ background: '#0D1929', borderColor: '#374151' }}>
              <div className="text-xs text-gray-400 mb-3">Quick-create customer</div>
              <div className="grid grid-cols-2 gap-3 mb-3">
                {([['Code *', 'customer_code'], ['Name *', 'name'], ['Email', 'email'], ['Phone', 'phone']] as [string, string][]).map(([label, key]) => (
                  <div key={key}>
                    <div className="text-xs mb-1" style={{ color: '#6B7280' }}>{label}</div>
                    <input
                      value={(newCustomerForm as any)[key]}
                      onChange={(e) => setNewCustomerForm((p) => ({ ...p, [key]: e.target.value }))}
                      className={inputClass}
                      style={{ background: '#1E2A3A', borderColor: '#374151' }}
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={handleCreateCustomer}
                disabled={creatingCustomer}
                className="px-3 py-1.5 rounded text-xs font-medium text-white"
                style={{ background: '#f97316', opacity: creatingCustomer ? 0.6 : 1 }}
              >
                {creatingCustomer ? 'Creating...' : 'Create & Select'}
              </button>
            </div>
          )}
        </div>

        {/* Quote Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Quote Details
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label="Quote Date" required>
              <input
                type="date"
                className={inputClass}
                style={inputStyle}
                value={form.quote_date}
                onChange={(e) => setForm((f) => ({ ...f, quote_date: e.target.value }))}
              />
            </FormField>
            <FormField label="Expiry Date" required>
              <input
                type="date"
                className={inputClass}
                style={inputStyle}
                value={form.expiry_date}
                onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))}
              />
            </FormField>
            <FormField label="Currency">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}
                placeholder="SGD"
              />
            </FormField>
          </div>
        </div>

        {/* Line Items */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Line Items
          </div>
          <div className="space-y-2 mb-3">
            {form.line_items.map((item, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  placeholder="Description"
                  value={item.description}
                  onChange={(e) => updateLineItem(i, 'description', e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ flex: 3, background: '#1E2A3A', borderColor: '#374151' }}
                />
                <input
                  placeholder="Qty"
                  type="number"
                  value={item.quantity}
                  onChange={(e) => updateLineItem(i, 'quantity', parseFloat(e.target.value) || 1)}
                  className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ flex: 1, background: '#1E2A3A', borderColor: '#374151' }}
                />
                <input
                  placeholder="Price"
                  type="number"
                  value={item.unit_price}
                  onChange={(e) => updateLineItem(i, 'unit_price', parseFloat(e.target.value) || 0)}
                  className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ flex: 1, background: '#1E2A3A', borderColor: '#374151' }}
                />
                <div className="text-sm text-right" style={{ flex: 1, color: '#9CA3AF' }}>
                  {(item.quantity * item.unit_price).toLocaleString('en-SG', { minimumFractionDigits: 2 })}
                </div>
                {form.line_items.length > 1 && (
                  <button
                    onClick={() => removeLineItem(i)}
                    className="px-2 py-1 rounded text-xs"
                    style={{ background: 'rgba(220,38,38,0.15)', color: '#dc2626' }}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between">
            <button
              onClick={addLineItem}
              className="px-3 py-1.5 rounded text-xs"
              style={{ background: '#1E2A3A', color: '#9CA3AF', border: '1px solid #374151' }}
            >
              + Add Line
            </button>
            <div className="text-sm font-semibold" style={{ color: '#F9FAFB' }}>
              Subtotal: {form.currency} {subtotal.toLocaleString('en-SG', { minimumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <FormField label="Notes">
            <textarea
              className={`${inputClass} resize-none`}
              style={inputStyle}
              rows={3}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Additional notes..."
            />
          </FormField>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex justify-end gap-3 pb-6">
        <button
          onClick={() => navigate('/mission-control/sales/quotes')}
          className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving || !form.customer_id}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{
            background: '#f97316',
            opacity: saving || !form.customer_id ? 0.6 : 1,
          }}
        >
          {saving ? (isEdit ? 'Saving...' : 'Creating...') : (isEdit ? 'Save Changes' : 'Create Quote')}
        </button>
      </div>
    </div>
  )
}
