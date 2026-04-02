import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'

type FormData = {
  name: string
  company_name: string
  email: string
  phone: string
  currency: string
  payment_terms: number
  industry: string
  location: string
  account_manager: string
  customer_type: string
  is_active: boolean
}

const EMPTY_FORM: FormData = {
  name: '',
  company_name: '',
  email: '',
  phone: '',
  currency: 'SGD',
  payment_terms: 30,
  industry: '',
  location: '',
  account_manager: '',
  customer_type: 'buyer',
  is_active: true,
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

export default function SalesCustomerFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = !!id

  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(isEdit)

  useEffect(() => {
    portalApi.getFinanceEntities().then((r) => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!isEdit || !entityId) return
    setLoading(true)
    portalApi.getFinanceCustomers(entityId).then((r) => {
      const custs = r.data?.data || []
      const customer = custs.find((c: any) => c.id === id)
      if (customer) {
        setForm({
          name: customer.name || '',
          company_name: customer.company_name || '',
          email: customer.email || '',
          phone: customer.phone || '',
          currency: customer.currency || 'SGD',
          payment_terms: customer.payment_terms ?? 30,
          industry: customer.industry || '',
          location: customer.location || '',
          account_manager: customer.account_manager || '',
          customer_type: customer.customer_type || 'buyer',
          is_active: customer.is_active !== false,
        })
      }
    }).catch(() => {}).finally(() => setLoading(false))
  }, [entityId, id, isEdit])

  const set = (key: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm((f) => ({ ...f, [key]: e.target.value }))
    }

  async function handleSubmit() {
    setSaving(true)
    setError(null)
    try {
      if (isEdit) {
        await portalApi.updateFinanceCustomer(id!, { ...form, entity_id: entityId })
        navigate(`/mission-control/sales/customers/${id}`)
      } else {
        await portalApi.createFinanceCustomer({ ...form, entity_id: entityId })
        navigate('/mission-control/sales/customers')
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to save customer')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(isEdit ? `/mission-control/sales/customers/${id}` : '/mission-control/sales/customers')}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          {isEdit ? 'Edit Customer' : 'New Customer'}
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

        {/* Basic Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Customer Information
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Name" required>
              <input
                className={inputClass}
                style={inputStyle}
                value={form.name}
                onChange={set('name')}
                placeholder="Customer Name"
              />
            </FormField>
            <FormField label="Company Name">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.company_name}
                onChange={set('company_name')}
                placeholder="Acme Corp"
              />
            </FormField>
            <FormField label="Email">
              <input
                type="email"
                className={inputClass}
                style={inputStyle}
                value={form.email}
                onChange={set('email')}
                placeholder="contact@acme.com"
              />
            </FormField>
            <FormField label="Phone">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.phone}
                onChange={set('phone')}
                placeholder="+65 9000 0000"
              />
            </FormField>
            <FormField label="Type" required>
              <select className={inputClass} style={inputStyle} value={form.customer_type} onChange={set('customer_type')}>
                <option value="buyer">Buyer</option>
                <option value="merchant">Merchant</option>
                <option value="partner">Partner</option>
              </select>
            </FormField>
            <FormField label="Status">
              <select
                className={inputClass}
                style={inputStyle}
                value={form.is_active ? 'active' : 'inactive'}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'active' }))}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </FormField>
          </div>
        </div>

        {/* Additional Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Additional Details
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Industry">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.industry}
                onChange={set('industry')}
                placeholder="Technology"
              />
            </FormField>
            <FormField label="Location">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.location}
                onChange={set('location')}
                placeholder="Singapore"
              />
            </FormField>
            <FormField label="Account Manager">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.account_manager}
                onChange={set('account_manager')}
                placeholder="Manager name"
              />
            </FormField>
          </div>
        </div>

        {/* Payment Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Payment Settings
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Currency">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.currency}
                onChange={set('currency')}
                placeholder="SGD"
              />
            </FormField>
            <FormField label="Payment Terms (days)">
              <input
                type="number"
                className={inputClass}
                style={inputStyle}
                value={form.payment_terms}
                onChange={(e) => setForm((f) => ({ ...f, payment_terms: Number(e.target.value) }))}
                min={0}
              />
            </FormField>
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex justify-end gap-3 pb-6">
        <button
          onClick={() => navigate(isEdit ? `/mission-control/sales/customers/${id}` : '/mission-control/sales/customers')}
          className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving || !form.name.trim()}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{
            background: '#f97316',
            opacity: saving || !form.name.trim() ? 0.6 : 1,
          }}
        >
          {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Customer'}
        </button>
      </div>
    </div>
  )
}
