import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  contacted: 'Contacted',
  qualified: 'Qualified',
  proposal: 'Proposal',
  closed_won: 'Won',
  closed_lost: 'Lost',
  disqualified: 'Disqualified',
}

const SOURCES = ['manual', 'linkedin', 'website', 'referral', 'event', 'email', 'web']

type FormData = {
  company_name: string
  contact_name: string
  contact_email: string
  contact_phone: string
  industry: string
  location: string
  source: string
  status: string
  notes: string
  lead_type: string
}

const EMPTY_FORM: FormData = {
  company_name: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  industry: '',
  location: '',
  source: 'manual',
  status: 'new',
  notes: '',
  lead_type: 'buyer',
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

export default function CRMLeadFormPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: (data: FormData) => portalApi.createLead(data as Record<string, unknown>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crm-leads'] })
      qc.invalidateQueries({ queryKey: ['crm-pipeline'] })
      navigate('/mission-control/crm')
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Failed to create lead')
    },
  })

  const set = (key: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      setForm((f) => ({ ...f, [key]: e.target.value }))
    }

  function handleSubmit() {
    setError(null)
    createMutation.mutate(form)
  }

  const isPending = createMutation.isPending

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/mission-control/crm')}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          New Lead
        </h1>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      <div className="rounded-xl border p-6 space-y-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        {/* Company Info */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Company Information
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Company Name" required>
              <input
                className={inputClass}
                style={inputStyle}
                value={form.company_name}
                onChange={set('company_name')}
                placeholder="Acme Corp"
              />
            </FormField>
            <FormField label="Industry">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.industry}
                onChange={set('industry')}
                placeholder="Technology"
              />
            </FormField>
            <FormField label="Location / Country">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.location}
                onChange={set('location')}
                placeholder="Singapore"
              />
            </FormField>
            <FormField label="Lead Type">
              <select className={inputClass} style={inputStyle} value={form.lead_type} onChange={set('lead_type')}>
                <option value="buyer">Buyer</option>
                <option value="merchant">Merchant</option>
                <option value="partner">Partner</option>
              </select>
            </FormField>
          </div>
        </div>

        {/* Contact Info */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Contact Information
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Contact Name">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.contact_name}
                onChange={set('contact_name')}
                placeholder="John Doe"
              />
            </FormField>
            <FormField label="Email">
              <input
                type="email"
                className={inputClass}
                style={inputStyle}
                value={form.contact_email}
                onChange={set('contact_email')}
                placeholder="john@acme.com"
              />
            </FormField>
            <FormField label="Phone">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.contact_phone}
                onChange={set('contact_phone')}
                placeholder="+65 9000 0000"
              />
            </FormField>
          </div>
        </div>

        {/* Lead Details */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: '#4B5563' }}>
            Lead Details
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Status">
              <select className={inputClass} style={inputStyle} value={form.status} onChange={set('status')}>
                {Object.entries(STATUS_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Source">
              <select className={inputClass} style={inputStyle} value={form.source} onChange={set('source')}>
                {SOURCES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </FormField>
          </div>
        </div>

        {/* Notes */}
        <div className="border-t pt-5" style={{ borderColor: '#1E2A3A' }}>
          <FormField label="Notes">
            <textarea
              className={`${inputClass} resize-none`}
              style={inputStyle}
              rows={4}
              value={form.notes}
              onChange={set('notes')}
              placeholder="Additional notes about this lead..."
            />
          </FormField>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex justify-end gap-3 pb-6">
        <button
          onClick={() => navigate('/mission-control/crm')}
          className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={isPending || !form.company_name.trim()}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{
            background: '#f97316',
            opacity: isPending || !form.company_name.trim() ? 0.6 : 1,
          }}
        >
          {isPending ? 'Creating...' : 'Create Lead'}
        </button>
      </div>
    </div>
  )
}
