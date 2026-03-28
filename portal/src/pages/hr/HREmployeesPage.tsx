import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import type { HREmployee } from '../../types'

const DEPARTMENTS = ['engineering', 'sales', 'marketing', 'finance', 'hr', 'operations', 'support', 'management', 'it']
const COUNTRIES = ['SG', 'MY', 'HK', 'AU', 'US', 'GB']

export default function HREmployeesPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [filterDept, setFilterDept] = useState('')
  const [filterCountry, setFilterCountry] = useState('')
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'inactive'>('active')

  const params: { department?: string; country?: string; is_active?: boolean; search?: string } = {}
  if (filterDept) params.department = filterDept
  if (filterCountry) params.country = filterCountry
  if (filterStatus !== 'all') params.is_active = filterStatus === 'active'
  if (search.trim()) params.search = search.trim()

  const { data, isLoading } = useQuery({
    queryKey: ['hr-employees', params],
    queryFn: () => portalApi.getHREmployees(params).then((r) => r.data),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      portalApi.patchHREmployeeStatus(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hr-employees'] }),
  })

  const employees: HREmployee[] = data?.data?.employees || []

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Employees
          </h1>
          <span className="text-sm" style={{ color: '#6B7280' }}>
            {employees.length > 0 ? `${employees.length} records` : ''}
          </span>
        </div>
        <button
          onClick={() => navigate('/mission-control/hr/employees/new')}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316' }}
        >
          + Add Employee
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search name or staff ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm text-white border outline-none w-56"
          style={{ background: '#1E2A3A', borderColor: '#374151' }}
        />
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
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as 'all' | 'active' | 'inactive')}
          className="px-3 py-2 rounded-lg text-sm text-white border outline-none"
          style={{ background: '#1E2A3A', borderColor: '#374151' }}
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
              <th className="px-4 py-3">Staff ID</th>
              <th className="py-3">Full Name</th>
              <th className="py-3">Department</th>
              <th className="py-3">Country</th>
              <th className="py-3">Job Title</th>
              <th className="py-3">Status</th>
              <th className="py-3 pr-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>
                  Loading...
                </td>
              </tr>
            )}
            {!isLoading && employees.map((emp) => (
              <tr
                key={emp.id}
                className="border-t cursor-pointer hover:bg-white/5 transition-colors"
                style={{ borderColor: '#1E2A3A' }}
                onClick={() => navigate(`/mission-control/hr/employees/${emp.id}`)}
              >
                <td className="px-4 py-2.5 text-gray-400 font-mono">{emp.staff_id}</td>
                <td className="py-2.5 text-gray-200 font-medium">{emp.full_name}</td>
                <td className="py-2.5 text-gray-400">{emp.department}</td>
                <td className="py-2.5 text-gray-400">{emp.country}</td>
                <td className="py-2.5 text-gray-400">{emp.job_title || '—'}</td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs"
                    style={{
                      background: emp.is_active ? 'rgba(34, 197, 94, 0.15)' : 'rgba(107, 114, 128, 0.2)',
                      color: emp.is_active ? '#86efac' : '#9CA3AF',
                    }}
                  >
                    {emp.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-2.5 pr-4" onClick={(e) => e.stopPropagation()}>
                  <div className="flex gap-2">
                    <button
                      onClick={() => navigate(`/mission-control/hr/employees/${emp.id}/edit`)}
                      className="px-2 py-1 rounded text-xs transition-colors hover:bg-orange-500/10"
                      style={{ color: '#f97316' }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => statusMutation.mutate({ id: emp.id, is_active: !emp.is_active })}
                      disabled={statusMutation.isPending}
                      className="px-2 py-1 rounded text-xs transition-colors"
                      style={{
                        color: emp.is_active ? '#EF4444' : '#86efac',
                        background: emp.is_active ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                      }}
                    >
                      {emp.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!isLoading && employees.length === 0 && (
              <tr>
                <td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>
                  No employees found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
