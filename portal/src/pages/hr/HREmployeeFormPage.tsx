import React, { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import type { HREmployee } from '../../types'

const DEPARTMENTS = ['engineering', 'sales', 'marketing', 'finance', 'hr', 'operations', 'support', 'management', 'it']
const COUNTRIES = ['SG', 'MY', 'HK', 'AU', 'US', 'GB']
const EMPLOYMENT_TYPES: Array<{ value: HREmployee['employment_type']; label: string }> = [
  { value: 'full_time', label: 'Full Time' },
  { value: 'part_time', label: 'Part Time' },
  { value: 'contract', label: 'Contract' },
]

type FormData = {
  staff_id: string
  full_name: string
  email: string
  phone: string
  department: string
  job_title: string
  employment_type: HREmployee['employment_type']
  country: string
  location_office: string
  manager_name: string
  manager_id: string
  hire_date: string
  probation_end_date: string
  annual_leave_days: number
  sick_leave_days: number
  other_leave_days: number
  profile_notes: string
  link_user: boolean
  user_id: string
}

const EMPTY_FORM: FormData = {
  staff_id: '',
  full_name: '',
  email: '',
  phone: '',
  department: 'hr',
  job_title: '',
  employment_type: 'full_time',
  country: 'SG',
  location_office: '',
  manager_name: '',
  manager_id: '',
  hire_date: '',
  probation_end_date: '',
  annual_leave_days: 14,
  sick_leave_days: 14,
  other_leave_days: 0,
  profile_notes: '',
  link_user: false,
  user_id: '',
}

function FormField({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
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

export default function HREmployeeFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = !!id
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)

  const { data: existingData } = useQuery({
    queryKey: ['hr-employee-edit', id],
    queryFn: () => portalApi.getHREmployee(id!).then((r) => r.data),
    enabled: isEdit,
  })

  const { data: employeesData } = useQuery({
    queryKey: ['hr-employees-list'],
    queryFn: () => portalApi.getHREmployees().then((r) => r.data),
  })
  const allEmployees: HREmployee[] = employeesData?.employees || employeesData || []

  useEffect(() => {
    const emp: HREmployee | null = existingData?.employee || existingData || null
    if (emp) {
      setForm({
        staff_id: emp.staff_id || '',
        full_name: emp.full_name || '',
        email: emp.email || '',
        phone: emp.phone || '',
        department: emp.department || 'hr',
        job_title: emp.job_title || '',
        employment_type: emp.employment_type || 'full_time',
        country: emp.country || 'SG',
        location_office: emp.location_office || '',
        manager_name: emp.manager_name || '',
        manager_id: emp.manager_id || '',
        hire_date: emp.hire_date || '',
        probation_end_date: emp.probation_end_date || '',
        annual_leave_days: emp.annual_leave_days ?? 14,
        sick_leave_days: emp.sick_leave_days ?? 14,
        other_leave_days: emp.other_leave_days ?? 0,
        profile_notes: emp.profile_notes || '',
        link_user: !!emp.user_id,
        user_id: emp.user_id || '',
      })
    }
  }, [existingData])

  useEffect(() => {
    if (!isEdit && form.staff_id === '' && allEmployees.length > 0) {
      const next = allEmployees.length + 1
      setForm((f) => ({ ...f, staff_id: `MZ-EMP-${String(next).padStart(3, '0')}` }))
    }
  }, [allEmployees, isEdit])

  const createMutation = useMutation({
    mutationFn: (data: Partial<HREmployee>) => portalApi.createHREmployee(data),
    onSuccess: (res) => {
      const newId = res.data?.id || res.data?.employee?.id
      navigate(newId ? `/mission-control/hr/employees/${newId}` : '/mission-control/hr/employees')
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Failed to create employee')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<HREmployee>) => portalApi.updateHREmployee(id!, data),
    onSuccess: () => navigate(`/mission-control/hr/employees/${id}`),
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Failed to update employee')
    },
  })

  function handleSubmit() {
    setError(null)
    const payload: Partial<HREmployee> = {
      staff_id: form.staff_id,
      full_name: form.full_name,
      email: form.email,
      phone: form.phone || null,
      department: form.department,
      job_title: form.job_title || null,
      employment_type: form.employment_type,
      country: form.country,
      location_office: form.location_office || null,
      manager_id: form.manager_id || null,
      hire_date: form.hire_date,
      probation_end_date: form.probation_end_date || null,
      annual_leave_days: form.annual_leave_days,
      sick_leave_days: form.sick_leave_days,
      other_leave_days: form.other_leave_days,
      profile_notes: form.profile_notes || null,
      user_id: form.link_user && form.user_id ? form.user_id : null,
    }
    if (isEdit) {
      updateMutation.mutate(payload)
    } else {
      createMutation.mutate(payload)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  const set = (key: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  const setNum = (key: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [key]: Number(e.target.value) }))
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(isEdit ? `/mission-control/hr/employees/${id}` : '/mission-control/hr/employees')}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back
        </button>
        <span style={{ color: '#374151' }}>/</span>
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          {isEdit ? 'Edit Employee' : 'New Employee'}
        </h1>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      <div className="rounded-xl border p-6 space-y-6" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormField label="Staff ID" required>
            <input className={inputClass} style={inputStyle} value={form.staff_id} onChange={set('staff_id')} placeholder="EMP-001" />
          </FormField>
          <FormField label="Full Name" required>
            <input className={inputClass} style={inputStyle} value={form.full_name} onChange={set('full_name')} />
          </FormField>
          <FormField label="Email" required>
            <input type="email" className={inputClass} style={inputStyle} value={form.email} onChange={set('email')} />
          </FormField>
          <FormField label="Phone">
            <input className={inputClass} style={inputStyle} value={form.phone} onChange={set('phone')} placeholder="+65 9000 0000" />
          </FormField>
          <FormField label="Department" required>
            <select className={inputClass} style={inputStyle} value={form.department} onChange={set('department')}>
              {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </FormField>
          <FormField label="Job Title">
            <input className={inputClass} style={inputStyle} value={form.job_title} onChange={set('job_title')} />
          </FormField>
          <FormField label="Employment Type">
            <select className={inputClass} style={inputStyle} value={form.employment_type} onChange={set('employment_type')}>
              {EMPLOYMENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </FormField>
          <FormField label="Country" required>
            <select className={inputClass} style={inputStyle} value={form.country} onChange={set('country')}>
              {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </FormField>
          <FormField label="Office Location">
            <input className={inputClass} style={inputStyle} value={form.location_office} onChange={set('location_office')} placeholder="Singapore HQ" />
          </FormField>
          <FormField label="Manager">
            <select
              className={inputClass}
              style={inputStyle}
              value={form.manager_id}
              onChange={(e) => {
                const selected = allEmployees.find((emp) => emp.id === e.target.value)
                setForm((f) => ({
                  ...f,
                  manager_id: e.target.value,
                  manager_name: selected?.full_name || '',
                }))
              }}
            >
              <option value="">— No Manager —</option>
              {allEmployees
                .filter((emp) => emp.is_active && emp.id !== id)
                .map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.full_name} ({emp.staff_id})
                  </option>
                ))}
            </select>
          </FormField>
          <FormField label="Hire Date" required>
            <input type="date" className={inputClass} style={inputStyle} value={form.hire_date} onChange={set('hire_date')} />
          </FormField>
          <FormField label="Probation End Date">
            <input type="date" className={inputClass} style={inputStyle} value={form.probation_end_date} onChange={set('probation_end_date')} />
          </FormField>
        </div>

        <div className="border-t pt-4" style={{ borderColor: '#1E2A3A' }}>
          <div className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Leave Entitlement</div>
          <div className="grid grid-cols-3 gap-4">
            <FormField label="Annual Leave Days" required>
              <input type="number" min={0} max={365} className={inputClass} style={inputStyle} value={form.annual_leave_days} onChange={setNum('annual_leave_days')} />
            </FormField>
            <FormField label="Sick Leave Days" required>
              <input type="number" min={0} max={365} className={inputClass} style={inputStyle} value={form.sick_leave_days} onChange={setNum('sick_leave_days')} />
            </FormField>
            <FormField label="Other Leave Days">
              <input type="number" min={0} max={365} className={inputClass} style={inputStyle} value={form.other_leave_days} onChange={setNum('other_leave_days')} />
            </FormField>
          </div>
        </div>

        <div className="border-t pt-4" style={{ borderColor: '#1E2A3A' }}>
          <FormField label="Profile Notes">
            <textarea
              className={`${inputClass} resize-none`}
              style={inputStyle}
              rows={3}
              value={form.profile_notes}
              onChange={set('profile_notes')}
            />
          </FormField>
        </div>

        <div className="border-t pt-4" style={{ borderColor: '#1E2A3A' }}>
          <div className="flex items-center gap-3 mb-3">
            <label className="text-sm text-gray-300">Link to User Account</label>
            <button
              onClick={() => setForm((f) => ({ ...f, link_user: !f.link_user }))}
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: form.link_user ? '#f97316' : '#374151' }}
            >
              <span
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                style={{ left: form.link_user ? '1.25rem' : '0.125rem' }}
              />
            </button>
          </div>
          {form.link_user && (
            <FormField label="User Account ID">
              <input className={inputClass} style={inputStyle} value={form.user_id} onChange={set('user_id')} placeholder="uuid of portal user" />
            </FormField>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex justify-end gap-3 pb-6">
        <button
          onClick={() => navigate(isEdit ? `/mission-control/hr/employees/${id}` : '/mission-control/hr/employees')}
          className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={isPending || !form.staff_id || !form.full_name || !form.email || !form.hire_date}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{
            background: '#f97316',
            opacity: isPending || !form.staff_id || !form.full_name || !form.email || !form.hire_date ? 0.6 : 1,
          }}
        >
          {isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Employee'}
        </button>
      </div>
    </div>
  )
}
