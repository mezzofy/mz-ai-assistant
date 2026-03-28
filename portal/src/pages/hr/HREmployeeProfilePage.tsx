import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { useAuthStore } from '../../stores/authStore'
import type { HREmployee, HRLeaveBalance, HRLeaveApplication } from '../../types'

const HR_MANAGE_ROLES = ['hr_staff', 'hr_manager', 'executive', 'admin']

type Tab = 'profile' | 'balance' | 'records'

function StatusBadge({ status }: { status: HRLeaveApplication['status'] }) {
  const config = {
    pending: { bg: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24' },
    approved: { bg: 'rgba(34, 197, 94, 0.15)', color: '#86efac' },
    rejected: { bg: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5' },
    cancelled: { bg: 'rgba(107, 114, 128, 0.2)', color: '#9CA3AF' },
  }
  const c = config[status] || config.cancelled
  return (
    <span className="px-2 py-0.5 rounded-full text-xs" style={{ background: c.bg, color: c.color }}>
      {status}
    </span>
  )
}

function ProfileField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs mb-1" style={{ color: '#6B7280' }}>{label}</div>
      <div className="text-sm text-gray-200">{value || '—'}</div>
    </div>
  )
}

export default function HREmployeeProfilePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const canManage = user?.role ? HR_MANAGE_ROLES.includes(user.role) : false

  const [activeTab, setActiveTab] = useState<Tab>('profile')
  const [balanceYear, setBalanceYear] = useState(new Date().getFullYear())
  const [showLeaveModal, setShowLeaveModal] = useState(false)

  const { data: profileData, isLoading } = useQuery({
    queryKey: ['hr-employee', id],
    queryFn: () => portalApi.getHREmployeeProfile(id!).then((r) => r.data),
    enabled: !!id,
  })

  const { data: balanceData } = useQuery({
    queryKey: ['hr-leave-balance', id, balanceYear],
    queryFn: () => portalApi.getHRLeaveBalance(id!, balanceYear).then((r) => r.data),
    enabled: !!id && activeTab === 'balance',
  })

  const { data: leaveData } = useQuery({
    queryKey: ['hr-leave-apps', id],
    queryFn: () => portalApi.getLeaveApplications({ employee_id: id }).then((r) => r.data),
    enabled: !!id && activeTab === 'records',
  })

  const cancelLeaveMutation = useMutation({
    mutationFn: (leaveId: string) => portalApi.updateLeaveStatus(leaveId, 'cancelled'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hr-leave-apps', id] }),
  })

  const emp: HREmployee | null = profileData?.data?.employee || profileData?.employee || null
  const balances: HRLeaveBalance[] = balanceData?.data?.balances || []
  const leaveApps: HRLeaveApplication[] = leaveData?.data?.applications || []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span style={{ color: '#6B7280' }}>Loading...</span>
      </div>
    )
  }

  if (!emp) {
    return (
      <div className="flex items-center justify-center py-20">
        <span style={{ color: '#EF4444' }}>Employee not found</span>
      </div>
    )
  }

  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  const tabs: { key: Tab; label: string }[] = [
    { key: 'profile', label: 'Profile' },
    { key: 'balance', label: 'Leave Balance' },
    { key: 'records', label: 'Leave Records' },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/mission-control/hr/employees')}
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            ← Employees
          </button>
          <span style={{ color: '#374151' }}>/</span>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {emp.full_name}
          </h1>
          <span
            className="px-2 py-0.5 rounded text-xs font-mono"
            style={{ background: '#1E2A3A', color: '#9CA3AF' }}
          >
            {emp.staff_id}
          </span>
          <span
            className="px-2 py-0.5 rounded-full text-xs"
            style={{
              background: emp.is_active ? 'rgba(34, 197, 94, 0.15)' : 'rgba(107, 114, 128, 0.2)',
              color: emp.is_active ? '#86efac' : '#9CA3AF',
            }}
          >
            {emp.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        {canManage && (
          <button
            onClick={() => navigate(`/mission-control/hr/employees/${id}/edit`)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316' }}
          >
            Edit
          </button>
        )}
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

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="rounded-xl border p-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
            <ProfileField label="Staff ID" value={<span className="font-mono">{emp.staff_id}</span>} />
            <ProfileField label="Full Name" value={emp.full_name} />
            <ProfileField label="Email" value={emp.email} />
            <ProfileField label="Phone" value={emp.phone} />
            <ProfileField label="Department" value={emp.department} />
            <ProfileField label="Job Title" value={emp.job_title} />
            <ProfileField label="Employment Type" value={emp.employment_type?.replace('_', ' ')} />
            <ProfileField label="Country" value={emp.country} />
            <ProfileField label="Office Location" value={emp.location_office} />
            <ProfileField label="Manager" value={emp.manager_name} />
            <ProfileField label="Hire Date" value={emp.hire_date} />
            <ProfileField label="Probation End" value={emp.probation_end_date} />
            <ProfileField label="Annual Leave Entitlement" value={`${emp.annual_leave_days} days`} />
            <ProfileField label="Sick Leave Entitlement" value={`${emp.sick_leave_days} days`} />
            <ProfileField label="Other Leave Entitlement" value={`${emp.other_leave_days} days`} />
            <ProfileField
              label="Linked User Account"
              value={emp.user_id ? <span className="font-mono text-xs">{emp.user_id}</span> : '—'}
            />
          </div>
          {emp.profile_notes && (
            <div className="mt-6">
              <div className="text-xs mb-2" style={{ color: '#6B7280' }}>Notes</div>
              <div className="text-sm text-gray-300 whitespace-pre-wrap">{emp.profile_notes}</div>
            </div>
          )}
        </div>
      )}

      {/* Leave Balance Tab */}
      {activeTab === 'balance' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">Year:</span>
            <select
              value={balanceYear}
              onChange={(e) => setBalanceYear(Number(e.target.value))}
              className="px-3 py-1.5 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
                  <th className="px-4 py-3">Leave Type</th>
                  <th className="py-3 text-right pr-4">Entitled</th>
                  <th className="py-3 text-right pr-4">Carried Over</th>
                  <th className="py-3 text-right pr-4">Taken</th>
                  <th className="py-3 text-right pr-4">Pending</th>
                  <th className="py-3 text-right pr-4">Remaining</th>
                </tr>
              </thead>
              <tbody>
                {balances.map((b) => (
                  <tr key={b.id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
                    <td className="px-4 py-2.5 text-gray-200">{b.leave_type_name || b.leave_type_code}</td>
                    <td className="py-2.5 text-right pr-4 text-gray-400">{b.entitled_days}</td>
                    <td className="py-2.5 text-right pr-4 text-gray-400">{b.carried_over}</td>
                    <td className="py-2.5 text-right pr-4 text-gray-400">{b.taken_days}</td>
                    <td className="py-2.5 text-right pr-4" style={{ color: '#fbbf24' }}>{b.pending_days}</td>
                    <td className="py-2.5 text-right pr-4 font-semibold text-white">{b.remaining_days}</td>
                  </tr>
                ))}
                {balances.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center" style={{ color: '#6B7280' }}>
                      No leave balance data for {balanceYear}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Leave Records Tab */}
      {activeTab === 'records' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowLeaveModal(true)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: '#f97316' }}
            >
              Apply Leave
            </button>
          </div>
          <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
                  <th className="px-4 py-3">Applied</th>
                  <th className="py-3">Leave Type</th>
                  <th className="py-3">Start</th>
                  <th className="py-3">End</th>
                  <th className="py-3">Days</th>
                  <th className="py-3">Status</th>
                  <th className="py-3 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {leaveApps.map((app) => {
                  const isFuture = new Date(app.start_date) > new Date()
                  const canCancel = (app.status === 'pending' || (app.status === 'approved' && isFuture))
                  return (
                    <tr key={app.id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
                      <td className="px-4 py-2.5 text-gray-400">
                        {new Date(app.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-2.5 text-gray-300">{app.leave_type_name}</td>
                      <td className="py-2.5 text-gray-400">{app.start_date}</td>
                      <td className="py-2.5 text-gray-400">{app.end_date}</td>
                      <td className="py-2.5 text-gray-400">{app.total_days}</td>
                      <td className="py-2.5"><StatusBadge status={app.status} /></td>
                      <td className="py-2.5 pr-4">
                        {canCancel && (
                          <button
                            onClick={() => cancelLeaveMutation.mutate(app.id)}
                            disabled={cancelLeaveMutation.isPending}
                            className="px-2 py-1 rounded text-xs transition-colors"
                            style={{ color: '#EF4444', background: 'rgba(239, 68, 68, 0.1)' }}
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {leaveApps.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-10 text-center" style={{ color: '#6B7280' }}>
                      No leave applications
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Leave Application Modal */}
      {showLeaveModal && id && (
        <HRLeaveApplicationModal
          employeeId={id}
          onClose={() => setShowLeaveModal(false)}
          onSuccess={() => {
            setShowLeaveModal(false)
            qc.invalidateQueries({ queryKey: ['hr-leave-apps', id] })
          }}
        />
      )}
    </div>
  )
}

function HRLeaveApplicationModal({
  employeeId,
  onClose,
  onSuccess,
}: {
  employeeId: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState({
    leave_type_id: '',
    start_date: '',
    end_date: '',
    half_day: false,
    reason: '',
  })
  const [calculatedDays, setCalculatedDays] = useState(0)

  const { data: typesData } = useQuery({
    queryKey: ['hr-leave-types'],
    queryFn: () => portalApi.getLeaveTypes().then((r) => r.data),
  })

  const leaveTypes = typesData?.leave_types || typesData || []

  const applyMutation = useMutation({
    mutationFn: () =>
      portalApi.applyLeave({
        employee_id: employeeId,
        leave_type_id: form.leave_type_id,
        start_date: form.start_date,
        end_date: form.end_date,
        half_day: form.half_day,
        total_days: calculatedDays,
        reason: form.reason || null,
        half_day_period: null,
        applied_via: 'portal',
      }),
    onSuccess,
  })

  function countWorkingDays(start: string, end: string): number {
    if (!start || !end) return 0
    const s = new Date(start)
    const e = new Date(end)
    if (e < s) return 0
    let count = 0
    const cur = new Date(s)
    while (cur <= e) {
      const day = cur.getDay()
      if (day !== 0 && day !== 6) count++
      cur.setDate(cur.getDate() + 1)
    }
    return count
  }

  function handleDateChange(field: 'start_date' | 'end_date', value: string) {
    const updated = { ...form, [field]: value }
    setForm(updated)
    const days = countWorkingDays(updated.start_date, updated.end_date)
    setCalculatedDays(updated.half_day ? 0.5 : days)
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="w-full max-w-md p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <h3 className="text-base font-semibold text-white mb-5">Apply Leave</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Leave Type</label>
            <select
              value={form.leave_type_id}
              onChange={(e) => setForm((f) => ({ ...f, leave_type_id: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              <option value="">Select leave type...</option>
              {leaveTypes.map((t: { id: string; name: string }) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Start Date</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => handleDateChange('start_date', e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                style={{ background: '#1E2A3A', borderColor: '#374151' }}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">End Date</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => handleDateChange('end_date', e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                style={{ background: '#1E2A3A', borderColor: '#374151' }}
              />
            </div>
          </div>
          {calculatedDays > 0 && (
            <div className="text-sm px-3 py-2 rounded-lg" style={{ background: 'rgba(249, 115, 22, 0.1)', color: '#f97316' }}>
              {calculatedDays} working day{calculatedDays !== 1 ? 's' : ''}
            </div>
          )}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-400">Half Day</label>
            <button
              onClick={() => {
                const newHalf = !form.half_day
                setForm((f) => ({ ...f, half_day: newHalf }))
                const days = countWorkingDays(form.start_date, form.end_date)
                setCalculatedDays(newHalf ? 0.5 : days)
              }}
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: form.half_day ? '#f97316' : '#374151' }}
            >
              <span
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                style={{ left: form.half_day ? '1.25rem' : '0.125rem' }}
              />
            </button>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Reason (optional)</label>
            <textarea
              value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
              rows={3}
              className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none resize-none"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-gray-400">
            Cancel
          </button>
          <button
            onClick={() => applyMutation.mutate()}
            disabled={applyMutation.isPending || !form.leave_type_id || !form.start_date || !form.end_date}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: '#f97316', opacity: !form.leave_type_id || !form.start_date || !form.end_date ? 0.5 : 1 }}
          >
            {applyMutation.isPending ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  )
}
