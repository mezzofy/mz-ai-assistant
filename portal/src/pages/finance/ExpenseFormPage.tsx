import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'

const inputClass = 'w-full px-3 py-2 rounded-lg text-sm text-white border outline-none'
const inputStyle = { background: '#1E2A3A', borderColor: '#374151' }

const DEFAULT_CATEGORIES = [
  'Travel', 'Meals & Entertainment', 'Office Supplies', 'Equipment',
  'Software & Subscriptions', 'Marketing', 'Professional Fees', 'Utilities', 'Rent', 'Other'
]

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

export default function ExpenseFormPage() {
  const navigate = useNavigate()

  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')
  const [vendors, setVendors] = useState<any[]>([])
  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [showNewCategory, setShowNewCategory] = useState(false)

  const [form, setForm] = useState({
    expense_date: new Date().toISOString().slice(0, 10),
    category: '',
    description: '',
    vendor_id: '',
    currency: 'SGD',
    amount: '',
    tax_amount: '',
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
    portalApi.getFinanceVendors(entityId).then(r => setVendors(r.data?.data || [])).catch(() => {})
  }, [entityId])

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const addCategory = () => {
    if (!newCategoryName.trim()) return
    setCategories(prev => [...prev, newCategoryName.trim()])
    setForm(f => ({ ...f, category: newCategoryName.trim() }))
    setNewCategoryName('')
    setShowNewCategory(false)
  }

  const handleSubmit = async () => {
    setError(null)
    setSaving(true)
    try {
      await portalApi.createExpense({
        entity_id: entityId,
        expense_date: form.expense_date,
        category: form.category,
        description: form.description,
        vendor_id: form.vendor_id || undefined,
        currency: form.currency,
        amount: parseFloat(form.amount) || 0,
        tax_amount: parseFloat(form.tax_amount) || 0,
      })
      navigate('/mission-control/finance/expenses')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create expense')
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
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>New Expense</h1>
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

        {/* Expense Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Expense Details</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Date" required>
              <input type="date" className={inputClass} style={inputStyle} value={form.expense_date} onChange={set('expense_date')} />
            </FormField>
            <div>
              <FormField label="Category" required>
                <div className="flex gap-2">
                  <select className={inputClass} style={inputStyle} value={form.category} onChange={set('category')}>
                    <option value="">— Select category —</option>
                    {categories.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <button
                    onClick={() => setShowNewCategory(v => !v)}
                    className="px-3 py-2 rounded-lg text-xs whitespace-nowrap"
                    style={{ background: '#1E2A3A', color: '#9CA3AF', border: '1px solid #374151', cursor: 'pointer' }}
                  >
                    + New
                  </button>
                </div>
              </FormField>
              {showNewCategory && (
                <div className="mt-2 flex gap-2">
                  <input
                    className={inputClass}
                    style={inputStyle}
                    value={newCategoryName}
                    onChange={e => setNewCategoryName(e.target.value)}
                    placeholder="Category name"
                    onKeyDown={e => e.key === 'Enter' && addCategory()}
                  />
                  <button
                    onClick={addCategory}
                    className="px-3 py-2 rounded-lg text-xs whitespace-nowrap text-white"
                    style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}
                  >
                    Add
                  </button>
                </div>
              )}
            </div>
            <div className="md:col-span-2">
              <FormField label="Description" required>
                <input className={inputClass} style={inputStyle} value={form.description} onChange={set('description')} placeholder="Expense description" />
              </FormField>
            </div>
            <FormField label="Vendor">
              <select className={inputClass} style={inputStyle} value={form.vendor_id} onChange={set('vendor_id')}>
                <option value="">— Select vendor (optional) —</option>
                {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </FormField>
          </div>
        </div>

        {/* Amount */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Amount</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Currency">
              <input className={inputClass} style={inputStyle} value={form.currency} onChange={set('currency')} placeholder="SGD" />
            </FormField>
            <FormField label="Amount" required>
              <input type="number" className={inputClass} style={inputStyle} value={form.amount} onChange={set('amount')} placeholder="0.00" min="0" />
            </FormField>
            <FormField label="Tax Amount">
              <input type="number" className={inputClass} style={inputStyle} value={form.tax_amount} onChange={set('tax_amount')} placeholder="0.00" min="0" />
            </FormField>
            {form.amount && (
              <div className="flex items-end">
                <div>
                  <div className="text-xs mb-1" style={{ color: '#6B7280' }}>Total</div>
                  <div className="text-lg font-semibold text-white">
                    {form.currency} {((parseFloat(form.amount) || 0) + (parseFloat(form.tax_amount) || 0)).toFixed(2)}
                  </div>
                </div>
              </div>
            )}
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
          disabled={saving || !entityId || !form.description.trim() || !form.amount || !form.category}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316', opacity: saving || !entityId || !form.description.trim() || !form.amount || !form.category ? 0.6 : 1 }}
        >
          {saving ? 'Creating...' : 'Create Expense'}
        </button>
      </div>
    </div>
  )
}
