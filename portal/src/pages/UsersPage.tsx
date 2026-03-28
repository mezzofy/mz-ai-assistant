import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { User } from '../types'

const DEPARTMENTS = ['finance', 'sales', 'marketing', 'support', 'management', 'hr', 'it']
const ROLES = [
  'admin', 'executive',
  'finance_viewer', 'finance_manager',
  'sales_rep', 'sales_manager',
  'marketing_creator', 'marketing_manager',
  'support_agent', 'support_manager',
  'hr_viewer', 'hr_staff', 'hr_manager',
  'legal_officer',
]

function Avatar({ name }: { name: string }) {
  return (
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
      style={{ background: '#1E2A3A', color: '#f97316' }}
    >
      {name?.charAt(0)?.toUpperCase() || '?'}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }, [text])
  return (
    <button
      onClick={copy}
      title="Copy full User ID"
      className="p-1 rounded transition-colors hover:bg-orange-500/10"
      style={{ color: copied ? '#00D4AA' : '#6B7280' }}
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      )}
    </button>
  )
}

export default function UsersPage() {
  const qc = useQueryClient()
  const [showNewModal, setShowNewModal] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deleteUser, setDeleteUser] = useState<User | null>(null)
  const [newForm, setNewForm] = useState({ email: '', name: '', department: 'sales', role: 'sales_rep' })
  const [lastInviteToken, setLastInviteToken] = useState<string | null>(null)
  const [editError, setEditError] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['users'],
    queryFn: () => portalApi.getUsers().then((r) => r.data),
    refetchInterval: 60000,
  })

  const createMutation = useMutation({
    mutationFn: () => portalApi.createUser(newForm),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setShowNewModal(false)
      setNewForm({ email: '', name: '', department: 'sales', role: 'sales_rep' })
      const token = response?.data?.invite_token
      if (token) {
        setLastInviteToken(token)
      }
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<{ name: string; department: string; role: string; is_active: boolean }> }) =>
      portalApi.updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setEditUser(null)
      setEditError(null)
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setEditError(msg || 'Failed to save changes')
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
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Users
          </h1>
          <span className="text-sm" style={{ color: '#6B7280' }}>
            {users.length > 0 ? `${users.length} users` : ''}
          </span>
        </div>
        <button
          onClick={() => setShowNewModal(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
          style={{ background: '#f97316' }}
        >
          + New User
        </button>
      </div>

      {lastInviteToken && (
        <div
          className="flex items-center justify-between px-4 py-3 rounded-lg border text-sm"
          style={{ background: 'rgba(249, 115, 22, 0.1)', borderColor: '#f97316' }}
        >
          <div>
            <span className="text-gray-300">Invite token created: </span>
            <code className="text-white font-mono px-2 py-0.5 rounded" style={{ background: '#1E2A3A' }}>
              {lastInviteToken}
            </code>
            <span className="text-gray-400 ml-2 text-xs">Share this with the user if the invite email was not delivered.</span>
          </div>
          <button
            onClick={() => setLastInviteToken(null)}
            className="text-gray-400 hover:text-white ml-4"
          >
            &times;
          </button>
        </div>
      )}

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
              <th className="py-3">User ID</th>
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
                <td className="py-2.5">
                  <div className="flex items-center gap-1">
                    <code
                      className="text-xs font-mono px-1.5 py-0.5 rounded"
                      style={{ background: '#1E2A3A', color: '#9CA3AF' }}
                      title={user.id}
                    >
                      {user.id.slice(0, 8)}…
                    </code>
                    <CopyButton text={user.id} />
                  </div>
                </td>
                <td className="py-2.5 pr-4">
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setEditUser(user); setEditError(null) }}
                      title="Edit"
                      className="p-1.5 rounded transition-colors hover:bg-orange-500/10"
                      style={{ color: '#f97316' }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                    </button>
                    <button
                      onClick={() => setDeleteUser(user)}
                      title="Deactivate"
                      className="p-1.5 rounded transition-colors hover:bg-red-500/10"
                      style={{ color: '#EF4444' }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                        <path d="M10 11v6M14 11v6"/>
                        <path d="M9 6V4h6v2"/>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={8} className="py-12 text-center" style={{ color: '#6B7280' }}>
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
                style={{ background: '#f97316' }}
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
                  style={{ background: editUser.is_active ? '#f97316' : '#374151' }}
                >
                  <span
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: editUser.is_active ? '1.25rem' : '0.125rem' }}
                  />
                </button>
              </div>
            </div>
            {editError && (
              <div className="mt-4 px-3 py-2 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#fca5a5' }}>
                {editError}
              </div>
            )}
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setEditUser(null); setEditError(null) }} className="px-4 py-2 rounded-lg text-sm text-gray-400">
                Cancel
              </button>
              <button
                onClick={() => updateMutation.mutate({
                  id: editUser.id,
                  data: { department: editUser.department, role: editUser.role, is_active: editUser.is_active },
                })}
                disabled={updateMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white"
                style={{ background: '#f97316' }}
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
