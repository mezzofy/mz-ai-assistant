import React, { useState, useEffect } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { portalApi } from '../../api/portal'

interface FinEntity {
  id: string
  name: string
}

interface TaxCode {
  id: string
  code: string
  name: string
}

interface Item {
  id: string
  entity_id: string
  item_code: string
  name: string
  description: string | null
  category: string
  unit: string
  unit_price: number
  currency: string
  tax_code_id: string | null
  is_active: boolean
}

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  product:      { bg: 'rgba(59,130,246,0.15)',  color: '#93C5FD' },
  service:      { bg: 'rgba(34,197,94,0.15)',   color: '#86EFAC' },
  subscription: { bg: 'rgba(139,92,246,0.15)',  color: '#C4B5FD' },
  other:        { bg: 'rgba(107,114,128,0.15)', color: '#9CA3AF' },
}

function getCategoryBadge(category: string) {
  return CATEGORY_COLORS[category?.toLowerCase()] ?? CATEGORY_COLORS.other
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
  name: '',
  description: '',
  category: 'service',
  unit: 'each',
  unit_price: '',
  currency: 'SGD',
  tax_code_id: '',
}

export default function ItemsPage() {
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [entityId, setEntityId] = useState<string>('')
  const [items, setItems] = useState<Item[]>([])
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([])
  const [loadingEntities, setLoadingEntities] = useState(true)
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
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
    setLoading(true)
    Promise.all([
      portalApi.getItems(entityId),
      portalApi.getTaxCodes(entityId),
    ])
      .then(([itemsRes, tcRes]) => {
        const itemData = itemsRes.data?.data ?? itemsRes.data ?? []
        setItems(Array.isArray(itemData) ? itemData : [])
        const tcData = tcRes.data?.data ?? tcRes.data ?? []
        setTaxCodes(Array.isArray(tcData) ? tcData : [])
      })
      .catch(() => { setItems([]); setTaxCodes([]) })
      .finally(() => setLoading(false))
  }, [entityId])

  const reloadItems = () => {
    if (!entityId) return
    portalApi.getItems(entityId)
      .then(r => {
        const data = r.data?.data ?? r.data ?? []
        setItems(Array.isArray(data) ? data : [])
      })
      .catch(() => setItems([]))
  }

  const openNew = () => {
    setEditingItem(null)
    setForm({ ...defaultForm })
    setError(null)
    setShowForm(true)
  }

  const openEdit = (item: Item) => {
    setEditingItem(item)
    setForm({
      name: item.name,
      description: item.description || '',
      category: item.category || 'service',
      unit: item.unit || 'each',
      unit_price: String(item.unit_price),
      currency: item.currency,
      tax_code_id: item.tax_code_id || '',
    })
    setError(null)
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditingItem(null)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setError('Name is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        entity_id: entityId,
        name: form.name.trim(),
        description: form.description || undefined,
        category: form.category,
        unit: form.unit,
        unit_price: parseFloat(form.unit_price) || 0,
        currency: form.currency || 'SGD',
        tax_code_id: form.tax_code_id || undefined,
      }
      if (editingItem) {
        await portalApi.updateItem(editingItem.id, payload)
      } else {
        await portalApi.createItem(payload)
      }
      closeForm()
      reloadItems()
    } catch (e: any) {
      const d = e?.response?.data
      const msg = typeof d?.detail === 'string'
        ? d.detail
        : Array.isArray(d?.detail)
          ? d.detail.map((x: any) => x.msg).join(', ')
          : d?.message || d?.error || `Failed to save item (${e?.response?.status ?? 'network error'})`
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await portalApi.deleteItem(id, entityId)
      setConfirmDeleteId(null)
      reloadItems()
    } catch {
      // silently ignore
    }
  }

  const formatPrice = (price: number, currency: string) => {
    return `${currency} ${price.toFixed(2)}`
  }

  const getTaxCodeLabel = (taxCodeId: string | null) => {
    if (!taxCodeId) return null
    const tc = taxCodes.find(t => t.id === taxCodeId)
    return tc ? tc.code : null
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
            Items
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            Manage products, services and subscriptions by entity
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
              + New Item
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
              {editingItem ? 'Edit Item' : 'New Item'}
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
            <FormField label="Name" required>
              <input
                className={inputClass}
                style={inputStyle}
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Item name"
              />
            </FormField>

            <FormField label="Category">
              <select
                className={inputClass}
                style={inputStyle}
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              >
                <option value="product">Product</option>
                <option value="service">Service</option>
                <option value="subscription">Subscription</option>
                <option value="other">Other</option>
              </select>
            </FormField>

            <FormField label="Unit">
              <select
                className={inputClass}
                style={inputStyle}
                value={form.unit}
                onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}
              >
                <option value="each">Each</option>
                <option value="hour">Hour</option>
                <option value="day">Day</option>
                <option value="kg">kg</option>
                <option value="box">Box</option>
                <option value="unit">Unit</option>
              </select>
            </FormField>

            <FormField label="Unit Price">
              <input
                type="number"
                step="0.0001"
                min="0"
                className={inputClass}
                style={inputStyle}
                value={form.unit_price}
                onChange={e => setForm(f => ({ ...f, unit_price: e.target.value }))}
                placeholder="0.00"
              />
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

            <FormField label="Tax Code">
              <select
                className={inputClass}
                style={inputStyle}
                value={form.tax_code_id}
                onChange={e => setForm(f => ({ ...f, tax_code_id: e.target.value }))}
              >
                <option value="">— None —</option>
                {taxCodes.map(tc => (
                  <option key={tc.id} value={tc.id}>
                    {tc.code} — {tc.name}
                  </option>
                ))}
              </select>
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
              {saving ? 'Saving...' : editingItem ? 'Save Changes' : 'Create Item'}
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
        {loadingEntities || loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            Loading...
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#6B7280' }}>
            {entityId ? 'No items found for this entity.' : 'Select an entity to view items.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1F2937', borderBottom: '1px solid #1E2A3A' }}>
                  {['Item Code', 'Name', 'Category', 'Unit', 'Unit Price', 'Tax Code', 'Active', 'Actions'].map(col => (
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
                {items.map((item, idx) => {
                  const badge = getCategoryBadge(item.category)
                  const isConfirmDelete = confirmDeleteId === item.id
                  const taxLabel = getTaxCodeLabel(item.tax_code_id)
                  return (
                    <tr
                      key={item.id}
                      style={{
                        borderBottom: '1px solid #1E2A3A',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.05)')}
                      onMouseLeave={e => (e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(31,41,55,0.4)')}
                    >
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                        {item.item_code}
                      </td>
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13 }}>
                        {item.name}
                        {item.description && (
                          <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>{item.description}</div>
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
                          {item.category}
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', color: '#9CA3AF', fontSize: 13 }}>
                        {item.unit}
                      </td>
                      <td style={{ padding: '10px 16px', color: '#F9FAFB', fontSize: 13, whiteSpace: 'nowrap' }}>
                        {formatPrice(typeof item.unit_price === 'number' ? item.unit_price : parseFloat(String(item.unit_price)) || 0, item.currency)}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {taxLabel ? (
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 12,
                              fontSize: 11,
                              fontWeight: 600,
                              background: 'rgba(249,115,22,0.12)',
                              color: '#FDBA74',
                            }}
                          >
                            {taxLabel}
                          </span>
                        ) : (
                          <span style={{ color: '#4B5563' }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>
                        {item.is_active ? (
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
                              onClick={() => handleDelete(item.id)}
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
                              onClick={() => openEdit(item)}
                              title="Edit"
                              className="p-1 rounded transition-colors"
                              style={{ color: '#6B7280' }}
                              onMouseEnter={e => (e.currentTarget.style.color = '#D1D5DB')}
                              onMouseLeave={e => (e.currentTarget.style.color = '#6B7280')}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(item.id)}
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
