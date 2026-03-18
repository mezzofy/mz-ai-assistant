import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { User } from '../types'

const DEPARTMENTS = ['finance', 'sales', 'marketing', 'support', 'management', 'hr', 'it']
const ROLES = ['admin', 'executive', 'manager', 'sales_rep', 'marketing_rep', 'support_rep', 'hr_rep', 'finance_rep']

function Avatar({ name }: { name: string }) {
  return (
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
      style={{ background: '#1E2A3A', color: '#6C63FF' }}
    >
      {name?.charAt(0)?.toUpperCase() || '?'}
    </div>
  )
}

export default function UsersPage() {
  const qc = useQueryClient()
  const [showNewModal, setShowNewModal] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deleteUser, setDeleteUser] = useState<User | null>(null)
  const [newForm, setNewForm] = useState({ email: '', name: '', department: 'sales', role: 'sales_rep' })

  const { data } = useQuery({
    queryKey: ['users'],
    queryFn: () => portalApi.getUsers().then((r) => r.data),
    refetchInterval: 60000,
  })

  const createMutation = useMutation({
    mutationFn: () => portalApi.createUser(newForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setShowNewModal(false)
      setNewForm({ email: '', name: '', department: 'sales', role: 'sales_rep' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<{ name: string; department: string; role: string; is_active: boolean }> }) =>
      portalApi.updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setEditUser(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => portalApi.deleteUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setDeleteUser(null)
    },
  })

  const users: User[] = data?.users || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Users
        </h1>
        <button
          onClick={() => setShowNewModal(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#6C63FF' }}
        >
          + New User
        </button>
      </div>

      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
              <th className="px-4 py-3">User</th>
              <th className="py-3">Department</th>
              <th className="py-3">Role</th>
              <th className="py-3">Status</th>
              <th className="py-3">Last Login</th>
              <th className="py-3">Sessions</th>
              <th className="py-3 pr-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={user.name} />
                    <div>
                      <div className="text-gray-200 font-medium">{user.name}</div>
                      <div style={{ color: '#6B7280' }}>{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="py-2.5 text-gray-400">{user.department}</td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded text-xs"
                    style={{ background: '#1E2A3A', color: '#9CA3AF' }}
                  >
                    {user.role}
                  </span>
                </td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs"
                    style={{
                      background: user.is_active ? 'rgba(0, 212, 170, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                      color: user.is_active ? '#00D4AA' : '#EF4444',
                    }}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-2.5 text-gray-400">
                  {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2.5 text-gray-400">{user.session_count ?? 0}</td>
                <td className="py-2.5 pr-4">
                  <div className="flex gap-2">
                    <button
                      onClick={() => setEditUser(user)}
                      className="px-2 py-1 rounded text-xs transition-colors"
                      style={{ color: '#6C63FF' }}
                    >
                      ✏
                    </button>
                    <button
                      onClick={() => setDeleteUser(user)}
                      className="px-2 py-1 rounded text-xs transition-colors hover:bg-red-500/10"
                      style={{ color: '#EF4444' }}
                    >
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={7} className="py-12 text-center" style={{ color: '#6B7280' }}>
                  No users
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* New User Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="w-full max-w-md p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <h3 className="text-base font-semibold text-white mb-5">Invite New User</h3>
            <div className="space-y-4">
              {([
                { label: 'Full Name', key: 'name', type: 'text' },
                { label: 'Email', key: 'email', type: 'email' },
              ] as { label: string; key: 'name' | 'email'; type: string }[]).map(({ label, key, type }) => (
                <div key={key}>
                  <label className="block text-xs text-gray-400 mb-1">{label}</label>
                  <input
                    type={type}
                    value={newForm[key]}
                    onChange={(e) => setNewForm((f) => ({ ...f, [key]: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                    style={{ background: '#1E2A3A', borderColor: '#374151' }}
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Department</label>
                <select
                  value={newForm.department}
                  onChange={(e) => setNewForm((f) => ({ ...f, department: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Role</label>
                <select
                  value={newForm.role}
                  onChange={(e) => setNewForm((f) => ({ ...f, role: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowNewModal(false)}
                className="px-4 py-2 rounded-lg text-sm text-gray-400"
              >
                Cancel
              </button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white"
                style={{ background: '#6C63FF' }}
              >
                {createMutation.isPending ? 'Sending...' : 'Send Invite'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editUser && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="w-full max-w-md p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <h3 className="text-base font-semibold text-white mb-5">Edit User</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Department</label>
                <select
                  value={editUser.department}
                  onChange={(e) => setEditUser((u) => u ? { ...u, department: e.target.value } : u)}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Role</label>
                <select
                  value={editUser.role}
                  onChange={(e) => setEditUser((u) => u ? { ...u, role: e.target.value } : u)}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs text-gray-400">Active</label>
                <button
                  onClick={() => setEditUser((u) => u ? { ...u, is_active: !u.is_active } : u)}
                  className="relative w-10 h-5 rounded-full transition-colors"
                  style={{ background: editUser.is_active ? '#6C63FF' : '#374151' }}
                >
                  <span
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: editUser.is_active ? '1.25rem' : '0.125rem' }}
                  />
                </button>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setEditUser(null)} className="px-4 py-2 rounded-lg text-sm text-gray-400">
                Cancel
              </button>
              <button
                onClick={() => updateMutation.mutate({
                  id: editUser.id,
                  data: { department: editUser.department, role: editUser.role, is_active: editUser.is_active },
                })}
                disabled={updateMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white"
                style={{ background: '#6C63FF' }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteUser && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="w-full max-w-sm p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <h3 className="text-base font-semibold text-white mb-2">Deactivate User</h3>
            <p className="text-sm mb-1" style={{ color: '#6B7280' }}>
              Soft-delete <span className="text-gray-200">{deleteUser.name}</span>?
            </p>
            <p className="text-xs mb-5" style={{ color: '#EF4444' }}>
              This will set deleted_at, deactivate the account, and blacklist all active tokens.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteUser(null)} className="px-4 py-2 rounded-lg text-sm text-gray-400">
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteUser.id)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm text-white"
                style={{ background: '#EF4444' }}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Deactivate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
