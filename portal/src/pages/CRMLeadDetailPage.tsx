import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { Lead } from '../types'

const STATUS_COLORS: Record<string, string> = {
  new: '#7A8FA6',
  contacted: '#4DA6FF',
  qualified: '#FFB84D',
  proposal: '#f97316',
  closed_won: '#00D4AA',
  closed_lost: '#EF4444',
  disqualified: '#6B7280',
}

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  contacted: 'Contacted',
  qualified: 'Qualified',
  proposal: 'Proposal',
  closed_won: 'Won',
  closed_lost: 'Lost',
  disqualified: 'Disqualified',
}

const ACTIVITY_ICONS: Record<string, string> = {
  created: '✦',
  status_changed: '→',
  assigned: '👤',
  note: '📝',
  call: '📞',
  meeting: '📅',
  email_sent: '✉️',
  follow_up_set: '⏰',
}

const ACTIVITY_ICON_COLORS: Record<string, string> = {
  created: '#f97316',
  status_changed: '#4DA6FF',
  assigned: '#FFB84D',
  note: '#9CA3AF',
  call: '#00D4AA',
  meeting: '#a78bfa',
  email_sent: '#60a5fa',
  follow_up_set: '#fbbf24',
}

interface LeadActivity {
  id: string
  lead_id: string
  actor_id: string | null
  actor_name: string | null
  type: string
  title: string
  body: string | null
  meta: Record<string, unknown> | null
  created_at: string
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

function LeadField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs mb-1" style={{ color: '#6B7280' }}>{label}</div>
      <div className="text-sm" style={{ color: '#E5E7EB' }}>{value || '—'}</div>
    </div>
  )
}

export default function CRMLeadDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [activityType, setActivityType] = useState('note')
  const [activityTitle, setActivityTitle] = useState('')
  const [activityBody, setActivityBody] = useState('')

  const [showConvertModal, setShowConvertModal] = useState(false)
  const [convertForm, setConvertForm] = useState({ name: '', company_name: '', email: '', phone: '', customer_type: 'buyer', currency: 'SGD', payment_terms: 30 })
  const [convertEntityId, setConvertEntityId] = useState('')
  const [convertEntities, setConvertEntities] = useState<any[]>([])
  const [converting, setConverting] = useState(false)
  const [convertToast, setConvertToast] = useState('')

  const { data: leadData, isLoading: leadLoading } = useQuery({
    queryKey: ['crm-lead-detail', id],
    queryFn: () => portalApi.getCrmLeadDetail(id!).then((r) => r.data),
    enabled: !!id,
  })

  const { data: activitiesData, isLoading: activitiesLoading } = useQuery({
    queryKey: ['crm-lead-activities', id],
    queryFn: () => portalApi.getCrmLeadActivities(id!).then((r) => r.data),
    enabled: !!id,
  })

  const addActivityMutation = useMutation({
    mutationFn: (data: { type: string; title: string; body?: string }) =>
      portalApi.addLeadActivity(id!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crm-lead-activities', id] })
      setActivityTitle('')
      setActivityBody('')
      setActivityType('note')
    },
  })

  const lead: Lead | null = leadData?.data?.lead || leadData?.lead || leadData?.data || (leadData?.id ? leadData as Lead : null)
  const activities: LeadActivity[] = activitiesData?.data?.activities || activitiesData?.activities || []

  // Load entities when convert modal opens
  React.useEffect(() => {
    if (!showConvertModal) return
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setConvertEntities(ents)
      if (ents.length > 0) setConvertEntityId(ents[0].id)
    })
  }, [showConvertModal])

  // Pre-populate from lead data when lead loads
  React.useEffect(() => {
    if (lead) {
      setConvertForm(f => ({
        ...f,
        name: (lead as any).contact_name || lead.company_name || '',
        company_name: lead.company_name || '',
        email: (lead as any).contact_email || (lead as any).email || '',
        phone: (lead as any).contact_phone || (lead as any).phone || '',
      }))
    }
  }, [lead])

  async function handleConvertToCustomer() {
    setConverting(true)
    try {
      const r = await portalApi.createFinanceCustomer({ entity_id: convertEntityId, ...convertForm })
      const newId = r.data?.data?.id
      setShowConvertModal(false)
      setConvertToast('Customer created successfully')
      setTimeout(() => setConvertToast(''), 4000)
      if (newId) navigate(`/mission-control/sales/customers/${newId}`)
    } catch {
      setConvertToast('Failed to create customer')
      setTimeout(() => setConvertToast(''), 4000)
    } finally {
      setConverting(false)
    }
  }

  if (leadLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span style={{ color: '#6B7280' }}>Loading...</span>
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="flex items-center justify-center py-20">
        <span style={{ color: '#EF4444' }}>Lead not found</span>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/mission-control/crm')}
            className="text-sm transition-colors"
            style={{ color: '#6B7280' }}
            onMouseOver={(e) => (e.currentTarget.style.color = '#E5E7EB')}
            onMouseOut={(e) => (e.currentTarget.style.color = '#6B7280')}
          >
            ← Leads
          </button>
          <span style={{ color: '#374151' }}>/</span>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {lead.company_name}
          </h1>
          <span
            className="px-2 py-0.5 rounded-full text-xs"
            style={{
              background: `${STATUS_COLORS[lead.status] || '#6B7280'}20`,
              color: STATUS_COLORS[lead.status] || '#6B7280',
            }}
          >
            {STATUS_LABELS[lead.status] || lead.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/mission-control/crm/leads/${id}/edit`)}
            className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
            style={{ background: '#f9731622', color: '#f97316', border: '1px solid #f9731644' }}>
            Edit Lead
          </button>
          <button onClick={() => setShowConvertModal(true)}
            className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
            style={{ background: '#16a34a22', color: '#16a34a', border: '1px solid #16a34a44' }}>
            Convert to Customer
          </button>
        </div>
      </div>

      {convertToast && (
        <div className="px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(0,212,170,0.15)', color: '#00D4AA', borderLeft: '3px solid #00D4AA' }}>
          ✓ {convertToast}
        </div>
      )}

      {/* Lead Info Card */}
      <div className="rounded-xl border p-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <div className="space-y-5">
          {/* Row 1: Company / Type / Industry / Location */}
          <div className="grid grid-cols-4 gap-6">
            <LeadField label="Company" value={lead.company_name} />
            <LeadField
              label="Type"
              value={((lead as any).lead_type || 'buyer').charAt(0).toUpperCase() + ((lead as any).lead_type || 'buyer').slice(1)}
            />
            <LeadField label="Industry" value={lead.industry} />
            <LeadField label="Location" value={lead.location} />
          </div>
          {/* Row 2: Contact Name / Email / Phone / Source */}
          <div className="grid grid-cols-4 gap-6">
            <LeadField label="Contact Name" value={lead.contact_name} />
            <LeadField label="Email" value={lead.contact_email} />
            <LeadField label="Phone" value={lead.contact_phone} />
            <LeadField label="Source" value={lead.source} />
          </div>
          {/* Row 3: Created At / Follow-up Date / Last Contacted */}
          <div className="grid grid-cols-3 gap-6">
            <LeadField
              label="Created At"
              value={lead.created_at ? new Date(lead.created_at).toLocaleDateString() : null}
            />
            <LeadField
              label="Follow-up Date"
              value={lead.follow_up_date ? new Date(lead.follow_up_date).toLocaleDateString() : null}
            />
            <LeadField
              label="Last Contacted"
              value={lead.last_contacted ? new Date(lead.last_contacted).toLocaleDateString() : null}
            />
          </div>
          {/* Row 4: Status / Assigned To */}
          <div className="grid grid-cols-4 gap-6">
            <LeadField label="Status" value={STATUS_LABELS[lead.status] || lead.status} />
            <LeadField
              label="Assigned To"
              value={(lead as any).pic_name || (lead as any).assigned_to_name || lead.assigned_to_email?.split('@')[0] || '—'}
            />
          </div>
          {/* Row 5: Notes */}
          {lead.notes && (
            <div>
              <div className="text-xs mb-2" style={{ color: '#6B7280' }}>Notes</div>
              <div className="text-sm whitespace-pre-wrap" style={{ color: '#D1D5DB' }}>{lead.notes}</div>
            </div>
          )}
        </div>
      </div>

      {/* Communication Log */}
      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <div className="px-5 py-4 border-b" style={{ borderColor: '#1E2A3A' }}>
          <h2 className="text-sm font-semibold text-white">Communication Log</h2>
        </div>

        {/* Timeline */}
        <div className="px-5 py-4 space-y-3">
          {activitiesLoading && (
            <div className="py-6 text-center text-sm" style={{ color: '#6B7280' }}>Loading...</div>
          )}
          {!activitiesLoading && activities.length === 0 && (
            <div className="py-6 text-center text-sm" style={{ color: '#6B7280' }}>
              No activity yet. Add the first note below.
            </div>
          )}
          {activities.map((act) => {
            const icon = ACTIVITY_ICONS[act.type] || '•'
            const iconColor = ACTIVITY_ICON_COLORS[act.type] || '#9CA3AF'
            return (
              <div key={act.id} className="flex gap-3 items-start">
                <div
                  className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs"
                  style={{ background: `${iconColor}18`, color: iconColor }}
                >
                  {icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: '#E5E7EB' }}>{act.title}</span>
                    {act.actor_name && (
                      <span className="text-xs" style={{ color: '#6B7280' }}>{act.actor_name}</span>
                    )}
                    <span className="text-xs" style={{ color: '#4B5563' }}>{timeAgo(act.created_at)}</span>
                  </div>
                  {act.body && (
                    <div className="mt-0.5 text-xs whitespace-pre-wrap" style={{ color: '#9CA3AF' }}>{act.body}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Add Activity Form */}
        <div className="px-5 py-4 border-t space-y-3" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-medium" style={{ color: '#9CA3AF' }}>Add Activity</div>
          <div className="flex gap-2 flex-wrap">
            {(['note', 'call', 'meeting', 'email_sent', 'follow_up_set'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setActivityType(t)}
                className="px-3 py-1 rounded-full text-xs transition-colors"
                style={{
                  background: activityType === t ? '#f97316' : '#1E2A3A',
                  color: activityType === t ? '#fff' : '#9CA3AF',
                  border: `1px solid ${activityType === t ? '#f97316' : '#374151'}`,
                }}
              >
                {ACTIVITY_ICONS[t]} {t === 'email_sent' ? 'Email' : t === 'follow_up_set' ? 'Follow-up' : t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Title (required)"
              value={activityTitle}
              onChange={(e) => setActivityTitle(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            />
            <button
              onClick={() => {
                if (!activityTitle.trim()) return
                addActivityMutation.mutate({
                  type: activityType,
                  title: activityTitle.trim(),
                  body: activityBody.trim() || undefined,
                })
              }}
              disabled={addActivityMutation.isPending || !activityTitle.trim()}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ background: '#f97316' }}
            >
              {addActivityMutation.isPending ? 'Adding...' : 'Add'}
            </button>
          </div>
          <textarea
            placeholder="Details (optional)"
            value={activityBody}
            onChange={(e) => setActivityBody(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none resize-none"
            style={{ background: '#1E2A3A', borderColor: '#374151' }}
          />
        </div>
      </div>

      {showConvertModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>Convert to Customer</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Entity</div>
                <select value={convertEntityId} onChange={e => setConvertEntityId(e.target.value)}
                  style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%' }}>
                  {convertEntities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
              {[
                { label: 'Name *', key: 'name' },
                { label: 'Company', key: 'company_name' },
                { label: 'Email', key: 'email' },
                { label: 'Phone', key: 'phone' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input value={(convertForm as any)[f.key]} onChange={e => setConvertForm(p => ({ ...p, [f.key]: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              ))}
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Type</div>
                  <select value={convertForm.customer_type} onChange={e => setConvertForm(p => ({ ...p, customer_type: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%' }}>
                    <option value="buyer">Buyer</option>
                    <option value="merchant">Merchant</option>
                    <option value="partner">Partner</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Currency</div>
                  <input value={convertForm.currency} onChange={e => setConvertForm(p => ({ ...p, currency: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowConvertModal(false)}
                style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={handleConvertToCustomer} disabled={converting}
                style={{ background: '#16a34a', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                {converting ? 'Converting...' : 'Create Customer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
