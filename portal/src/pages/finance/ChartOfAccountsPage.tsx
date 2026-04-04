import React, { useState, useEffect } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { portalApi } from '../../api/portal'

interface FinEntity {
  id: string
  name: string
  base_currency: string
}

interface FinAccount {
  id: string
  entity_id: string
  category_id: string | null
  code: string
  name: string
  description: string | null
  currency: string
  account_type: string
  is_bank_account: boolean
  is_control: boolean
  allow_direct_posting: boolean
  is_active: boolean
}

interface AccountCategory {
  id: string
  name: string
  account_type: string
}

const ACCOUNT_TYPE_COLORS: Record<string, { bg: string; color: string }> = {
  asset:     { bg: 'rgba(59,130,246,0.15)',  color: '#93C5FD' },
  assets:    { bg: 'rgba(59,130,246,0.15)',  color: '#93C5FD' },
  liability: { bg: 'rgba(239,68,68,0.15)',   color: '#FCA5A5' },
  liabilities: { bg: 'rgba(239,68,68,0.15)', color: '#FCA5A5' },
  equity:    { bg: 'rgba(139,92,246,0.15)',  color: '#C4B5FD' },
  income:    { bg: 'rgba(34,197,94,0.15)',   color: '#86EFAC' },
  revenue:   { bg: 'rgba(34,197,94,0.15)',   color: '#86EFAC' },
  expense:   { bg: 'rgba(249,115,22,0.15)',  color: '#FDBA74' },
  expenses:  { bg: 'rgba(249,115,22,0.15)',  color: '#FDBA74' },
}

function getAccountTypeBadge(accountType: string) {
  const key = accountType.toLowerCase()
  return ACCOUNT_TYPE_COLORS[key] ?? { bg: 'rgba(107,114,128,0.15)', color: '#9CA3AF' }
}

const selectStyle: React.CSSProperties = {
  background: '#1E2A3A',
  border: '1px solid #374151',
  color: '#F9FAFB',
  borderRadius: 6,
  padding: '8px 12px',
  fontSize: 13,
  minWidth: 220,
  outline: 'none',
}

const inputClass = 'w-full px-3 py-2 rounded-lg text-sm text-white border outline-none'
const inputStyle = { background: '#1E2A3A', borderColor: '#374151' }

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

const defaultForm = {
  category_id: '',
  code: '',
  name: '',
  description: '',
  currency: 'SGD',
  is_bank_account: false,
  is_control: false,
  allow_direct_posting: true,
}

export default function ChartOfAccountsPage() {
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [entityId, setEntityId] = useState<string>('')
  const [accounts, setAccounts] = useState<FinAccount[]>([])
  const [categories, setCategories] = useState<AccountCategory[]>([])
  const [loadingEntities, setLoadingEntities] = useState(true)
  const [loadingAccounts, setLoadingAccounts] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingAccount, setEditingAccount] = useState<FinAccount | null>(null)
  const [form, setForm] = useState({ ...defaultForm })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  useEffect(() => {
    setLoadingEntities(true)
    portalApi.getFinanceEntities()
      .then(r => {
        const ents: FinEntity[] = r.data?.data || []
        setEntities(ents)
        if (ents.length > 0) setEntityId(ents[0].id)
      })
      .catch(() => {})
      .finally(() => setLoadingEntities(false))
  }, [])

  useEffect(() => {
    if (!entityId) return
    setLoadingAccounts(true)
    Promise.all([
      portalApi.getFinanceAccounts(entityId),
      portalApi.getFinanceAccountCategories(entityId),
    ])
      .then(([acctRes, catRes]) => {
        const data = acctRes.data?.data ?? acctRes.data ?? []
        setAccounts(Array.isArray(data) ? data : [])
        const cats = catRes.data?.data ?? catRes.data ?? []
        setCategories(Array.isArray(cats) ? cats : [])
      })
      .catch(() => { setAccounts([]); setCategories([]) })
      .finally(() => setLoadingAccounts(false))
  }, [entityId])

  const reloadAccounts = () => {
    if (!entityId) return
    portalApi.getFinanceAccounts(entityId)
      .then(r => {
        const data = r.data?.data ?? r.data ?? []
        setAccounts(Array.isArray(data) ? data : [])
      })
      .catch(() => setAccounts([]))
  }

  const openNew = () => {
    setEditingAccount(null)
    setForm({ ...defaultForm })
    setError(null)
    setShowForm(true)
  }

  const openEdit = (acct: FinAccount) => {
    setEditingAccount(acct)
    setForm({
      category_id: acct.category_id || '',
      code: acct.code,
      name: acct.name,
      description: acct.description || '',
      currency: acct.currency,
      is_bank_account: acct.is_bank_account,
      is_control: acct.is_control,
      allow_direct_posting: acct.allow_direct_posting ?? true,
    })
    setError(null)
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditingAccount(null)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!form.code.trim() || !form.name.trim()) {
      setError('Code and Name are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        entity_id: entityId,
        category_id: form.category_id || undefined,
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description || undefined,
        currency: form.currency || 'SGD',
        is_bank_account: form.is_bank_account,
        is_control: form.is_control,
        allow_direct_posting: form.allow_direct_posting,
      }
      if (editingAccount) {
        await portalApi.updateFinanceAccount(editingAccount.id, payload)
      } else {
        await portalApi.createFinanceAccount(payload)
      }
      closeForm()
      reloadAccounts()
    } catch (e: any) {
      const d = e?.response?.data
      const msg = typeof d?.detail === 'string'
        ? d.detail
        : Array.isArray(d?.detail)
          ? d.detail.map((x: any) => x.msg).join(', ')
          : d?.message || d?.error || `Failed to save account (${e?.response?.status ?? 'network error'})`
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await portalApi.deleteFinanceAccount(id, entityId)
      setConfirmDeleteId(null)
      reloadAccounts()
    } catch (e: any) {
      // silently ignore — row stays
    }
  }

  return (
    <div className="space-y-5" style={{ minHeight: '100%' }}>
      {/* Page Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1
            className="text-2xl font-bold text-white"
            style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}
          >
            Chart of Accounts
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            Manage accounts by entity
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Entity Selector */}
          {!loadingEntities && entities.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs" style={{ color: '#9CA3AF' }}>Entity</label>
              <select
                value={entityId}
                onChange={e => { setEntityId(e.target.value); setShowForm(false) }}
                style={selectStyle}
              >
                {entities.map(ent => (
                  <option key={ent.id} value={ent.id}>{ent.name}</option>
                ))}
              </select>
            </div>
          )}

          {entityId && (
            <button
              onClick={openNew}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
              style={{ background: '#f97316' }}
            >
              + New Account
            </button>
          )}
        </div>
      </div>

      {/* Inline Form Panel */}
      {showForm && (
        <div
          className="rounded-xl border p-5 space-y-4"
          style={{ background: '#1F2937', borderColor: '#374151' }}
        >
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">
              {editingAccount ? 'Edit Account' : 'New Account'}
            </h2>
            <button
              onClick={closeForm}
              className="text-sm"
              style={{ color: '#6B7280' }}
            >
              ✕ Cancel
            </button>
          </div>

          {error && (
            <div className="px-4 py-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', color: '#fca5a5' }}>
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Category">
              <select
                className={inputClass}
                style={inputStyle}
                value={form.category_id}
                onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))}
              >
                <option value="">— None —</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name} ({cat.account_type})
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Currency">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                placeholder="SGD"
              />
            </FormField>

            <FormField label="Code" required>
              <input
                className={inputClass}
                style={inputStyle}
                value={form.code}
                onChange={e => setForm(f => ({ ...f, code: e.target.value }))}
                placeholder="e.g. 1001"
              />
            </FormField>

            <FormField label="Name" required>
              <input
                className={inputClass}
                style={inputStyle}
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Account name"
              />
            </FormField>
          </div>

          <FormField label="Description">
            <textarea
              className={inputClass}
              style={{ ...inputStyle, resize: 'vertical', minHeight: 64 }}
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Optional description"
            />
          </FormField>

          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: '#D1D5DB' }}>
              <input
                type="checkbox"
                checked={form.is_bank_account}
                onChange={e => setForm(f => ({ ...f, is_bank_account: e.target.checked }))}
                style={{ accentColor: '#f97316' }}
              />
              Is Bank Account
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: '#D1D5DB' }}>
              <input
                type="checkbox"
                checked={form.is_control}
                onChange={e => setForm(f => ({ ...f, is_control: e.target.checked }))}
                style={{ accentColor: '#f97316' }}
              />
              Is Control Account
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: '#D1D5DB' }}>
              <input
                type="checkbox"
                checked={form.allow_direct_posting}
                onChange={e => setForm(f => ({ ...f, allow_direct_posting: e.target.checked }))}
                style={{ accentColor: '#f97316' }}
              />
              Allow Direct Posting
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={closeForm}
              className="px-4 py-2 rounded-lg text-sm transition-colors"
              style={{ color: '#9CA3AF' }}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="px-5 py-2 rounded-lg text-sm font-medium text-white transition-all"
              style={{ background: '#f97316', opacity: saving ? 0.6 : 1 }}
            >
              {saving ? 'Saving...' : editingAccount ? 'Save Changes' : 'Create Account'}
            </button>
          </div>
        </div>
      )}

      {/* Table Card */}
      <div
        style={{
          background: '#111827',
          border: '1px solid #1E2A3A',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {loadingEntities || loadingAccounts ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            Loading...
          </div>
        ) : accounts.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            {entityId ? 'No accounts found for this entity.' : 'Select an entity to view accounts.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1F2937', borderBottom: '1px solid #1E2A3A' }}>
                  {['Code', 'Name', 'Account Type', 'Currency', 'Bank Acct', 'Active', 'Actions'].map(col => (
                    <th
                      key={col}
                      style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: '#4B5563',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accounts.map((acct, idx) => {
                  const badge = getAccountTypeBadge(acct.account_type)
                  const isConfirmDelete = confirmDeleteId === acct.id
                  return (
                    <tr
                      key={acct.id}
                      style={{
                        borderBottom: '1px solid #1E2A3A',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.05)')}
                      onMouseLeave={e => (e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)')}
                    >
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                        {acct.code}
                      </td>
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13 }}>
                        {acct.name}
                        {acct.description && (
                          <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>{acct.description}</div>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 10px',
                            borderRadius: 12,
                            fontSize: 11,
                            fontWeight: 600,
                            textTransform: 'capitalize',
                            background: badge.bg,
                            color: badge.color,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {acct.account_type}
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', color: '#9CA3AF', fontSize: 13 }}>
                        {acct.currency}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {acct.is_bank_account ? (
                          <span style={{ color: '#86EFAC' }}>Yes</span>
                        ) : (
                          <span style={{ color: '#4B5563' }}>No</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {acct.is_active ? (
                          <span style={{ color: '#86EFAC' }}>Active</span>
                        ) : (
                          <span style={{ color: '#6B7280' }}>Inactive</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px', whiteSpace: 'nowrap' }}>
                        {isConfirmDelete ? (
                          <span className="flex items-center gap-2">
                            <span style={{ fontSize: 12, color: '#FCA5A5' }}>Delete?</span>
                            <button
                              onClick={() => handleDelete(acct.id)}
                              className="px-2 py-1 rounded text-xs font-medium"
                              style={{ background: 'rgba(239,68,68,0.2)', color: '#FCA5A5' }}
                            >
                              Yes
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="px-2 py-1 rounded text-xs font-medium"
                              style={{ background: 'rgba(107,114,128,0.2)', color: '#9CA3AF' }}
                            >
                              No
                            </button>
                          </span>
                        ) : (
                          <span className="flex items-center gap-2">
                            <button
                              onClick={() => openEdit(acct)}
                              title="Edit"
                              className="p-1 rounded transition-colors"
                              style={{ color: '#6B7280' }}
                              onMouseEnter={e => (e.currentTarget.style.color = '#D1D5DB')}
                              onMouseLeave={e => (e.currentTarget.style.color = '#6B7280')}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(acct.id)}
                              title="Delete"
                              className="p-1 rounded transition-colors"
                              style={{ color: '#6B7280' }}
                              onMouseEnter={e => (e.currentTarget.style.color = '#EF4444')}
                              onMouseLeave={e => (e.currentTarget.style.color = '#6B7280')}
                            >
                              <Trash2 size={14} />
                            </button>
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
