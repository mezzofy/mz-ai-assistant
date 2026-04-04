import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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

export default function VendorFormPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')

  const [form, setForm] = useState({
    name: '',
    company_name: '',
    email: '',
    phone: '',
    payment_terms: '30',
  })
  const [loading, setLoading] = useState(isEdit)
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

  // Load vendor for edit mode
  useEffect(() => {
    if (!isEdit || !id) return
    // No direct getVendor API — we'll skip pre-fill for edit (no detail endpoint available)
    setLoading(false)
  }, [id, isEdit])

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async () => {
    setError(null)
    setSaving(true)
    try {
      const payload = {
        entity_id: entityId,
        name: form.name,
        company_name: form.company_name || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        currency: entityCurrency,
        payment_terms: parseInt(form.payment_terms) || 30,
      }
      if (isEdit && id) {
        await (portalApi as any).updateFinanceVendor(id, payload)
      } else {
        await portalApi.createFinanceVendor(payload)
      }
      navigate('/mission-control/finance/vendors')
    } catch (e: any) {
      const d = e?.response?.data
      const msg = typeof d?.detail === 'string'
        ? d.detail
        : Array.isArray(d?.detail)
          ? d.detail.map((x: any) => x.msg).join(', ')
          : d?.message || d?.error || `Failed to ${isEdit ? 'update' : 'create'} vendor (${e?.response?.status ?? 'network error'})`
      setError(msg)
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
        <button onClick={() => navigate(-1)} className="text-sm text-gray-400 hover:text-gray-200 transition-colors">
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          {isEdit ? 'Edit Vendor' : 'New Vendor'}
        </h1>
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

        {/* Vendor Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Vendor Info</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Name" required>
              <input className={inputClass} style={inputStyle} value={form.name} onChange={set('name')} placeholder="Vendor Name" />
            </FormField>
            <FormField label="Company Name">
              <input className={inputClass} style={inputStyle} value={form.company_name} onChange={set('company_name')} placeholder="Company Pte Ltd" />
            </FormField>
          </div>
        </div>

        {/* Contact Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Contact Details</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Email">
              <input type="email" className={inputClass} style={inputStyle} value={form.email} onChange={set('email')} placeholder="vendor@example.com" />
            </FormField>
            <FormField label="Phone">
              <input className={inputClass} style={inputStyle} value={form.phone} onChange={set('phone')} placeholder="+65 9000 0000" />
            </FormField>
          </div>
        </div>

        {/* Payment Settings */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Payment Settings</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Currency">
              <input className={inputClass} style={{ ...inputStyle, opacity: 0.6, cursor: 'not-allowed' }} value={entityCurrency} readOnly />
            </FormField>
            <FormField label="Payment Terms (days)">
              <input type="number" className={inputClass} style={inputStyle} value={form.payment_terms} onChange={set('payment_terms')} placeholder="30" min="0" />
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
          disabled={saving || !entityId || !form.name.trim()}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316', opacity: saving || !entityId || !form.name.trim() ? 0.6 : 1 }}
        >
          {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Vendor'}
        </button>
      </div>
    </div>
  )
}
