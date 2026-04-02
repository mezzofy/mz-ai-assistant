import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
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

export default function CRMPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [country, setCountry] = useState('')
  const [countryInput, setCountryInput] = useState('')
  const [editLead, setEditLead] = useState<Lead | null>(null)

  const qc = useQueryClient()

  const { data: pipelineData } = useQuery({
    queryKey: ['crm-pipeline'],
    queryFn: () => portalApi.getCrmPipeline().then(r => r.data),
    refetchInterval: 60000,
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['crm-leads', page, statusFilter, search, country],
    queryFn: () => portalApi.getCrmLeads(page, statusFilter || undefined, search || undefined, country || undefined).then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: countriesData } = useQuery({
    queryKey: ['crm-countries'],
    queryFn: () => portalApi.getCrmCountries().then(r => r.data),
  })
  const countries: string[] = countriesData?.countries || []

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => portalApi.getUsers().then(r => r.data),
  })
  const users: User[] = usersData?.users || []

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => portalApi.updateLead(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crm-leads'] })
      qc.invalidateQueries({ queryKey: ['crm-countries'] })
      setEditLead(null)
    },
  })

  const leads: Lead[] = data?.leads || []
  const totalPages = data?.total_pages || 1
  const pipeline = pipelineData?.pipeline || []

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setCountry(countryInput)
    setPage(1)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Leads
          </h1>
          <span className="text-sm" style={{ color: '#6B7280' }}>
            {data?.total !== undefined ? `${data.total} leads` : ''}
          </span>
        </div>
        <button
          onClick={() => navigate('/mission-control/crm/leads/new')}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316' }}
        >
          + New Lead
        </button>
      </div>

      {/* Pipeline summary */}
      {pipeline.length > 0 && (
        <div className="grid grid-cols-3 lg:grid-cols-7 gap-3">
          {Object.keys(STATUS_COLORS).map((s) => {
            const stage = pipeline.find((p: { status: string; count: number }) => p.status === s)
            return (
              <button
                key={s}
                onClick={() => { setStatusFilter(statusFilter === s ? '' : s); setPage(1) }}
                className="rounded-xl border p-3 text-center transition-all hover:bg-white/5"
                style={{
                  background: statusFilter === s ? `${STATUS_COLORS[s]}20` : '#111827',
                  borderColor: statusFilter === s ? STATUS_COLORS[s] : '#1E2A3A',
                }}
              >
                <div className="text-xl font-bold" style={{ color: STATUS_COLORS[s] }}>
                  {stage?.count || 0}
                </div>
                <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>{STATUS_LABELS[s]}</div>
              </button>
            )
          })}
        </div>
      )}

      {/* Search + filter bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          type="text"
          placeholder="Search company..."
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm text-white border outline-none flex-1"
          style={{ background: '#111827', borderColor: '#1E2A3A' }}
        />
        <select
          value={countryInput}
          onChange={e => setCountryInput(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
          style={{ background: '#111827', borderColor: '#1E2A3A', width: '270px' }}
        >
          <option value="">All Countries</option>
          {countries.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <button
          type="submit"
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: '#f97316' }}
        >
          Search
        </button>
        {(statusFilter || search || country) && (
          <button
            type="button"
            onClick={() => { setStatusFilter(''); setSearch(''); setSearchInput(''); setCountry(''); setCountryInput(''); setPage(1) }}
            className="px-4 py-2 rounded-lg text-sm"
            style={{ background: '#1E2A3A', color: '#6B7280' }}
          >
            Clear
          </button>
        )}
      </form>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>
          Failed to load leads: {(error as { message?: string }).message}
        </div>
      )}

      {/* Leads table */}
      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
              <th className="px-4 py-3">Company</th>
              <th className="py-3">Contact</th>
              <th className="py-3">Industry</th>
              <th className="py-3">Source</th>
              <th className="py-3">Status</th>
              <th className="py-3">Type</th>
              <th className="py-3">Assigned To</th>
              <th className="py-3">Follow-up</th>
              <th className="py-3">Created</th>
              <th className="py-3 pr-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={10} className="py-12 text-center" style={{ color: '#6B7280' }}>Loading...</td></tr>
            )}
            {leads.map((lead) => (
              <tr
                key={lead.id}
                className="border-t hover:bg-white/5 transition-colors cursor-pointer"
                style={{ borderColor: '#1E2A3A' }}
                onClick={() => navigate(`/mission-control/crm/leads/${lead.id}`)}
              >
                <td className="px-4 py-2.5">
                  <div className="text-gray-200 font-medium">{lead.company_name}</div>
                  {lead.location && <div style={{ color: '#6B7280' }}>{lead.location}</div>}
                </td>
                <td className="py-2.5">
                  <div className="text-gray-300">{lead.contact_name}</div>
                  <div style={{ color: '#6B7280' }}>{lead.contact_email}</div>
                </td>
                <td className="py-2.5 text-gray-400">{lead.industry || '—'}</td>
                <td className="py-2.5 text-gray-400">{lead.source || '—'}</td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs"
                    style={{
                      background: `${STATUS_COLORS[lead.status] || '#6B7280'}20`,
                      color: STATUS_COLORS[lead.status] || '#6B7280',
                    }}
                  >
                    {STATUS_LABELS[lead.status] || lead.status}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{ background: '#374151', color: '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500, textTransform: 'capitalize' }}>
                    {(lead as any).lead_type || 'buyer'}
                  </span>
                </td>
                <td className="py-2.5 text-gray-400">
                  {lead.assigned_to_name || lead.assigned_to_email?.split('@')[0] || '—'}
                </td>
                <td className="py-2.5 text-gray-400">
                  {lead.follow_up_date ? new Date(lead.follow_up_date).toLocaleDateString() : '—'}
                </td>
                <td className="py-2.5 text-gray-400">
                  {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2.5 pr-4">
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditLead(lead) }}
                    title="Edit"
                    className="p-1.5 rounded transition-colors hover:bg-orange-500/10"
                    style={{ color: '#f97316' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && leads.length === 0 && !error && (
              <tr><td colSpan={10} className="py-12 text-center" style={{ color: '#6B7280' }}>No leads found</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs" style={{ color: '#6B7280' }}>
        <span>Page {page} of {totalPages} · {data?.total || 0} total leads</span>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg disabled:opacity-40" style={{ background: '#1E2A3A', color: '#E5E7EB' }}>
            ← Prev
          </button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="px-3 py-1.5 rounded-lg disabled:opacity-40" style={{ background: '#1E2A3A', color: '#E5E7EB' }}>
            Next →
          </button>
        </div>
      </div>

      {/* Edit Lead Modal */}
      {editLead && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-3xl rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A', padding: '1em', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 className="text-base font-semibold text-white mb-4">Edit Lead</h3>
            <div className="space-y-4">
              {/* Row 1: Company / Type / Industry / Location */}
              <div className="grid grid-cols-4 gap-3">
                {(['company_name', 'industry', 'location'] as const).map((key) => (
                  <div key={key}>
                    <label className="block text-xs text-gray-400 mb-1">
                      {key === 'company_name' ? 'Company Name' : key === 'industry' ? 'Industry' : 'Location / Country'}
                    </label>
                    <input
                      type="text"
                      value={(editLead[key] as string) || ''}
                      onChange={e => setEditLead(l => l ? { ...l, [key]: e.target.value } : l)}
                      className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                      style={{ background: '#1E2A3A', borderColor: '#374151' }}
                    />
                  </div>
                ))}
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Type</label>
                  <select
                    value={(editLead as any).lead_type || 'buyer'}
                    onChange={e => setEditLead(prev => prev ? { ...prev, lead_type: e.target.value } as any : null)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  >
                    <option value="buyer">Buyer</option>
                    <option value="merchant">Merchant</option>
                    <option value="partner">Partner</option>
                  </select>
                </div>
              </div>
              {/* Row 2: Contact Name / Email / Phone / Source */}
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Contact Name</label>
                  <input
                    type="text"
                    value={editLead.contact_name || ''}
                    onChange={e => setEditLead(l => l ? { ...l, contact_name: e.target.value } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Email</label>
                  <input
                    type="email"
                    value={editLead.contact_email || ''}
                    onChange={e => setEditLead(l => l ? { ...l, contact_email: e.target.value } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Phone</label>
                  <input
                    type="text"
                    value={editLead.contact_phone || ''}
                    onChange={e => setEditLead(l => l ? { ...l, contact_phone: e.target.value } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Source</label>
                  <select
                    value={editLead.source || 'manual'}
                    onChange={e => setEditLead(l => l ? { ...l, source: e.target.value } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  >
                    {['manual', 'linkedin', 'website', 'referral', 'event', 'email', 'web'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
              {/* Row 3: Status / Assigned To */}
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Status</label>
                  <select
                    value={editLead.status}
                    onChange={e => setEditLead(l => l ? { ...l, status: e.target.value } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  >
                    {Object.entries(STATUS_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs text-gray-400 mb-1">Assigned To</label>
                  <select
                    value={editLead.assigned_to || ''}
                    onChange={e => setEditLead(l => l ? { ...l, assigned_to: e.target.value || null } : l)}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  >
                    <option value="">— Unassigned —</option>
                    {users.map(u => (
                      <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                    ))}
                  </select>
                </div>
              </div>
              {/* Row 4: Notes */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Notes</label>
                <textarea
                  value={editLead.notes || ''}
                  onChange={e => setEditLead(l => l ? { ...l, notes: e.target.value } : l)}
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none resize-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setEditLead(null)} className="px-4 py-2 rounded-lg text-sm text-gray-400">Cancel</button>
              <button
                onClick={() => updateMutation.mutate({
                  id: editLead.id,
                  data: {
                    company_name: editLead.company_name,
                    contact_name: editLead.contact_name,
                    contact_email: editLead.contact_email,
                    contact_phone: editLead.contact_phone || undefined,
                    industry: editLead.industry || undefined,
                    location: editLead.location || undefined,
                    source: editLead.source,
                    status: editLead.status,
                    lead_type: (editLead as any).lead_type || 'buyer',
                    notes: editLead.notes || undefined,
                    assigned_to: editLead.assigned_to || undefined,
                  },
                })}
                disabled={updateMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: '#f97316' }}
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
