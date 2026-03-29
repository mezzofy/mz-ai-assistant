import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { useAuthStore } from '../../stores/authStore'
import type { HRLeaveDashboard, HRLeaveApplication, HRLeaveBalance } from '../../types'

const DEPARTMENTS = ['engineering', 'sales', 'marketing', 'finance', 'hr', 'operations', 'support', 'management', 'it']
const COUNTRIES = ['SG', 'MY', 'HK', 'AU', 'US', 'GB']
const APPROVER_ROLES = ['hr_staff', 'hr_manager', 'executive', 'admin']

type Tab = 'summary' | 'approvals'

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg p-4 border" style={{ background: 'rgba(31, 41, 55, 0.5)', borderColor: '#374151' }}>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-xs" style={{ color: '#6B7280' }}>{label}</div>
    </div>
  )
}

function downloadCSV(data: HRLeaveDashboard['employee_summaries']) {
  const header = ['Staff ID', 'Name', 'Department', 'Country', 'Annual Taken', 'Annual Remaining', 'Sick Taken', 'Sick Remaining', 'Pending']
  const rows = data.map((emp) => {
    const annual = emp.leave_balances.find((b) => b.leave_type_code?.toLowerCase().includes('annual') || b.leave_type_name?.toLowerCase().includes('annual'))
    const sick = emp.leave_balances.find((b) => b.leave_type_code?.toLowerCase().includes('sick') || b.leave_type_name?.toLowerCase().includes('sick'))
    return [
      emp.staff_id,
      emp.full_name,
      emp.department,
      emp.country,
      annual?.taken_days ?? '',
      annual?.remaining_days ?? '',
      sick?.taken_days ?? '',
      sick?.remaining_days ?? '',
      emp.pending_applications,
    ]
  })
  const csv = [header, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `hr-leave-summary-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function HRLeaveManagementPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const canApprove = user?.role ? APPROVER_ROLES.includes(user.role) : false

  const [activeTab, setActiveTab] = useState<Tab>('summary')
  const [filterDept, setFilterDept] = useState('')
  const [filterCountry, setFilterCountry] = useState('')
  const [filterYear, setFilterYear] = useState(new Date().getFullYear())

  // Reject flow
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [rejectComment, setRejectComment] = useState('')

  const { data: dashData, isLoading: dashLoading } = useQuery({
    queryKey: ['hr-dashboard', filterYear, filterDept, filterCountry],
    queryFn: () =>
      portalApi.getHRLeaveDashboard({
        year: filterYear,
        ...(filterDept ? { department: filterDept } : {}),
        ...(filterCountry ? { country: filterCountry } : {}),
      }).then((r) => r.data),
    enabled: activeTab === 'summary',
  })

  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['hr-pending'],
    queryFn: () => portalApi.getPendingApprovals().then((r) => r.data),
    enabled: activeTab === 'approvals' && canApprove,
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status, comment }: { id: string; status: string; comment?: string }) =>
      portalApi.updateLeaveStatus(id, status, comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hr-pending'] })
      qc.invalidateQueries({ queryKey: ['hr-dashboard'] })
      setRejectingId(null)
      setRejectComment('')
    },
  })

  const dashboard: HRLeaveDashboard | null = dashData?.data?.dashboard || dashData?.data || dashData?.dashboard || null
  const summaries = dashboard?.employee_summaries || []
  const pendingApps: HRLeaveApplication[] = pendingData?.data?.applications || pendingData?.applications || []

  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  const tabs: { key: Tab; label: string }[] = [
    { key: 'summary', label: 'Leave Summary' },
    ...(canApprove ? [{ key: 'approvals' as Tab, label: 'Pending Approvals' }] : []),
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Leave Management
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b" style={{ borderColor: '#1E2A3A' }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className="px-4 py-2.5 text-sm font-medium transition-colors"
            style={{
              color: activeTab === t.key ? '#f97316' : '#6B7280',
              borderBottom: activeTab === t.key ? '2px solid #f97316' : '2px solid transparent',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <select
              value={filterDept}
              onChange={(e) => setFilterDept(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              <option value="">All Departments</option>
              {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select
              value={filterCountry}
              onChange={(e) => setFilterCountry(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              <option value="">All Countries</option>
              {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select
              value={filterYear}
              onChange={(e) => setFilterYear(Number(e.target.value))}
              className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <div className="flex-1" />
            {summaries.length > 0 && (
              <button
                onClick={() => downloadCSV(summaries)}
                className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors hover:bg-white/5"
                style={{ borderColor: '#374151', color: '#9CA3AF' }}
              >
                Export CSV
              </button>
            )}
          </div>

          {/* Stat Cards */}
          {dashboard && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatCard label="Total Active Employees" value={dashboard.total_active_employees} />
              <StatCard label="On Leave Today" value={dashboard.on_leave_today} />
              <StatCard label="Pending Approvals" value={dashboard.pending_approvals} />
              <StatCard label="Leaves This Month" value={dashboard.leaves_this_month} />
            </div>
          )}

          {/* Summary Table */}
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
                  <th className="px-4 py-3">Staff ID</th>
                  <th className="py-3">Name</th>
                  <th className="py-3">Dept</th>
                  <th className="py-3">Country</th>
                  <th className="py-3 text-right pr-3">Annual (Taken/Rem)</th>
                  <th className="py-3 text-right pr-3">Sick (Taken/Rem)</th>
                  <th className="py-3 text-right pr-4">Pending</th>
                </tr>
              </thead>
              <tbody>
                {dashLoading && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>Loading...</td>
                  </tr>
                )}
                {!dashLoading && summaries.map((emp) => {
                  const annual = emp.leave_balances.find(
                    (b) => b.leave_type_code?.toLowerCase().includes('annual') || b.leave_type_name?.toLowerCase().includes('annual')
                  )
                  const sick = emp.leave_balances.find(
                    (b) => b.leave_type_code?.toLowerCase().includes('sick') || b.leave_type_name?.toLowerCase().includes('sick')
                  )
                  return (
                    <tr
                      key={emp.employee_id}
                      className="border-t cursor-pointer hover:bg-white/5 transition-colors"
                      style={{ borderColor: '#1E2A3A' }}
                      onClick={() => navigate(`/mission-control/hr/employees/${emp.employee_id}`)}
                    >
                      <td className="px-4 py-2.5 font-mono text-gray-400">{emp.staff_id}</td>
                      <td className="py-2.5 text-gray-200">{emp.full_name}</td>
                      <td className="py-2.5 text-gray-400">{emp.department}</td>
                      <td className="py-2.5 text-gray-400">{emp.country}</td>
                      <td className="py-2.5 text-right pr-3 text-gray-400">
                        {annual ? `${annual.taken_days} / ${annual.remaining_days}` : '—'}
                      </td>
                      <td className="py-2.5 text-right pr-3 text-gray-400">
                        {sick ? `${sick.taken_days} / ${sick.remaining_days}` : '—'}
                      </td>
                      <td className="py-2.5 text-right pr-4">
                        {emp.pending_applications > 0 ? (
                          <span className="px-2 py-0.5 rounded-full text-xs" style={{ background: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24' }}>
                            {emp.pending_applications}
                          </span>
                        ) : (
                          <span style={{ color: '#6B7280' }}>0</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {!dashLoading && summaries.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>No data</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pending Approvals Tab */}
      {activeTab === 'approvals' && canApprove && (
        <div className="space-y-4">
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
                  <th className="px-4 py-3">Employee</th>
                  <th className="py-3">Leave Type</th>
                  <th className="py-3">Start</th>
                  <th className="py-3">End</th>
                  <th className="py-3">Days</th>
                  <th className="py-3">Applied</th>
                  <th className="py-3">Reason</th>
                  <th className="py-3 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingLoading && (
                  <tr>
                    <td colSpan={8} className="py-12 text-center" style={{ color: '#6B7280' }}>Loading...</td>
                  </tr>
                )}
                {!pendingLoading && pendingApps.map((app) => (
                  <React.Fragment key={app.id}>
                    <tr className="border-t" style={{ borderColor: '#1E2A3A' }}>
                      <td className="px-4 py-2.5 text-gray-200">{app.employee_name}</td>
                      <td className="py-2.5 text-gray-400">{app.leave_type_name}</td>
                      <td className="py-2.5 text-gray-400">{app.start_date}</td>
                      <td className="py-2.5 text-gray-400">{app.end_date}</td>
                      <td className="py-2.5 text-gray-400">{app.total_days}</td>
                      <td className="py-2.5 text-gray-400">{new Date(app.created_at).toLocaleDateString()}</td>
                      <td className="py-2.5 text-gray-400 max-w-xs truncate">{app.reason || '—'}</td>
                      <td className="py-2.5 pr-4">
                        {rejectingId === app.id ? (
                          <div className="flex flex-col gap-1 min-w-32">
                            <input
                              type="text"
                              placeholder="Comment (optional)"
                              value={rejectComment}
                              onChange={(e) => setRejectComment(e.target.value)}
                              className="px-2 py-1 rounded text-xs text-white border outline-none"
                              style={{ background: '#1E2A3A', borderColor: '#374151' }}
                            />
                            <div className="flex gap-1">
                              <button
                                onClick={() => statusMutation.mutate({ id: app.id, status: 'rejected', comment: rejectComment || undefined })}
                                disabled={statusMutation.isPending}
                                className="flex-1 px-2 py-1 rounded text-xs text-white"
                                style={{ background: '#EF4444' }}
                              >
                                Confirm
                              </button>
                              <button
                                onClick={() => { setRejectingId(null); setRejectComment('') }}
                                className="flex-1 px-2 py-1 rounded text-xs text-gray-400 hover:text-gray-200"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => statusMutation.mutate({ id: app.id, status: 'approved' })}
                              disabled={statusMutation.isPending}
                              className="px-2 py-1 rounded text-xs font-medium text-white"
                              style={{ background: 'rgba(34, 197, 94, 0.2)', color: '#86efac' }}
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => setRejectingId(app.id)}
                              className="px-2 py-1 rounded text-xs font-medium"
                              style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5' }}
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  </React.Fragment>
                ))}
                {!pendingLoading && pendingApps.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-12 text-center" style={{ color: '#6B7280' }}>
                      No pending approvals
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
