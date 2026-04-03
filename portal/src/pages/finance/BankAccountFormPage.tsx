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

export default function BankAccountFormPage() {
  const navigate = useNavigate()

  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')

  const [form, setForm] = useState({
    bank_name: '',
    account_name: '',
    account_number: '',
    swift_code: '',
    currency: 'SGD',
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

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async () => {
    setError(null)
    setSaving(true)
    try {
      await portalApi.createBankAccount({ entity_id: entityId, ...form })
      navigate('/mission-control/finance/bank-accounts')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create bank account')
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
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>New Bank Account</h1>
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

        {/* Account Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Account Details</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Account Name" required>
              <input className={inputClass} style={inputStyle} value={form.account_name} onChange={set('account_name')} placeholder="Operating Account" />
            </FormField>
            <FormField label="Account Number">
              <input className={inputClass} style={inputStyle} value={form.account_number} onChange={set('account_number')} placeholder="1234-5678-9012" />
            </FormField>
            <FormField label="Currency" required>
              <input className={inputClass} style={inputStyle} value={form.currency} onChange={set('currency')} placeholder="SGD" />
            </FormField>
          </div>
        </div>

        {/* Bank Information */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>Bank Information</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Bank Name" required>
              <input className={inputClass} style={inputStyle} value={form.bank_name} onChange={set('bank_name')} placeholder="DBS Bank" />
            </FormField>
            <FormField label="SWIFT Code">
              <input className={inputClass} style={inputStyle} value={form.swift_code} onChange={set('swift_code')} placeholder="DBSSSGSG" />
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
          disabled={saving || !entityId || !form.bank_name.trim() || !form.account_name.trim()}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316', opacity: saving || !entityId || !form.bank_name.trim() || !form.account_name.trim() ? 0.6 : 1 }}
        >
          {saving ? 'Creating...' : 'Create Account'}
        </button>
      </div>
    </div>
  )
}
