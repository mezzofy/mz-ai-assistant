import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinVendor } from '../../types'

export default function Vendors() {
  const [vendors, setVendors] = useState<FinVendor[]>([])
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', vendor_code: '', company_name: '', email: '', currency: 'SGD', payment_terms: 30 })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!entityId) return
    setLoading(true)
    portalApi.getFinanceVendors(entityId)
      .then(r => setVendors(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  const handleSave = async () => {
    setSaving(true)
    try {
      await portalApi.createFinanceVendor({ ...form, entity_id: entityId })
      setShowModal(false)
      setForm({ name: '', vendor_code: '', company_name: '', email: '', currency: 'SGD', payment_terms: 30 })
      const r = await portalApi.getFinanceVendors(entityId)
      setVendors(r.data?.data || [])
    } catch { /* ignore */ } finally {
      setSaving(false)
    }
  }

  const inputStyle = { background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Vendors</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Vendor
          </button>
        </div>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : vendors.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No vendors found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Code', 'Name', 'Company', 'Email', 'Currency', 'Terms', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vendors.map(v => (
                <tr key={v.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{v.vendor_code}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{v.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{v.company_name || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{v.email || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{v.currency}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{v.payment_terms}d</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: v.is_active ? '#16a34a22' : '#6B728022', color: v.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {v.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* New Vendor Modal */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Vendor</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Vendor Code *', key: 'vendor_code' },
                { label: 'Name *', key: 'name' },
                { label: 'Company Name', key: 'company_name' },
                { label: 'Email', key: 'email' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} style={inputStyle} />
                </div>
              ))}
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Currency</div>
                  <input value={form.currency} onChange={e => setForm(p => ({ ...p, currency: e.target.value }))} style={inputStyle} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Payment Terms (days)</div>
                  <input type="number" value={form.payment_terms} onChange={e => setForm(p => ({ ...p, payment_terms: +e.target.value }))} style={inputStyle} />
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowModal(false)} style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={handleSave} disabled={saving} style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                {saving ? 'Saving...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
