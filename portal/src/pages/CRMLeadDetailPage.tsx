import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { Lead, User } from '../types'

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

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => portalApi.getUsers().then((r) => r.data),
  })
  const users: User[] = usersData?.users || []

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => portalApi.updateLead(id!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crm-lead-detail', id] })
      qc.invalidateQueries({ queryKey: ['crm-leads'] })
      qc.invalidateQueries({ queryKey: ['crm-lead-activities', id] })
    },
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
      </div>

      {/* Lead Info Card */}
      <div className="rounded-xl border p-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
          <LeadField label="Company" value={lead.company_name} />
          <LeadField label="Contact Name" value={lead.contact_name} />
          <LeadField label="Email" value={lead.contact_email} />
          <LeadField label="Phone" value={lead.contact_phone} />
          <LeadField label="Industry" value={lead.industry} />
          <LeadField label="Location" value={lead.location} />
          <LeadField label="Source" value={lead.source} />
          <div>
            <div className="text-xs mb-1" style={{ color: '#6B7280' }}>Status</div>
            <select
              value={lead.status}
              onChange={(e) => updateMutation.mutate({ status: e.target.value })}
              className="px-2 py-1 rounded-lg text-xs text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              {Object.entries(STATUS_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="text-xs mb-1" style={{ color: '#6B7280' }}>Assigned To</div>
            <select
              value={lead.assigned_to || ''}
              onChange={(e) => updateMutation.mutate({ assigned_to: e.target.value || null })}
              className="px-2 py-1 rounded-lg text-xs text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              <option value="">— Unassigned —</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="text-xs mb-1" style={{ color: '#6B7280' }}>Type</div>
            <select
              value={(lead as any).lead_type || 'buyer'}
              onChange={(e) => updateMutation.mutate({ lead_type: e.target.value })}
              className="px-2 py-1 rounded-lg text-xs text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              <option value="buyer">Buyer</option>
              <option value="merchant">Merchant</option>
              <option value="partner">Partner</option>
            </select>
          </div>
          <LeadField
            label="Follow-up Date"
            value={lead.follow_up_date ? new Date(lead.follow_up_date).toLocaleDateString() : null}
          />
          <LeadField
            label="Last Contacted"
            value={lead.last_contacted ? new Date(lead.last_contacted).toLocaleDateString() : null}
          />
          <LeadField
            label="Created At"
            value={lead.created_at ? new Date(lead.created_at).toLocaleDateString() : null}
          />
        </div>
        {lead.notes && (
          <div className="mt-6">
            <div className="text-xs mb-2" style={{ color: '#6B7280' }}>Notes</div>
            <div className="text-sm whitespace-pre-wrap" style={{ color: '#D1D5DB' }}>{lead.notes}</div>
          </div>
        )}
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
    </div>
  )
}
