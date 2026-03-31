import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinEntity } from '../../types'

export default function Entities() {
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ code: '', name: '', entity_type: 'subsidiary', country_code: 'SG', base_currency: 'SGD', tax_id: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    portalApi.getFinanceEntities()
      .then(r => setEntities(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await portalApi.createFinanceEntity(form)
      setShowModal(false)
      setForm({ code: '', name: '', entity_type: 'subsidiary', country_code: 'SG', base_currency: 'SGD', tax_id: '' })
      load()
    } catch { /* ignore */ } finally {
      setSaving(false)
    }
  }

  const inputStyle = { background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }
  const ENTITY_TYPES = ['subsidiary', 'holding', 'branch', 'group']

  return (
    <div style={{ padding: 24, color: '#F9FAFB' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Legal Entities</h1>
          <p style={{ color: '#6B7280', fontSize: 13, margin: '4px 0 0' }}>Finance settings — entity management</p>
        </div>
        <button onClick={() => setShowModal(true)}
          style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
          + New Entity
        </button>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : entities.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No entities found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Code', 'Name', 'Type', 'Country', 'Currency', 'Tax ID', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entities.map(e => (
                <tr key={e.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{e.code}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{e.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', textTransform: 'capitalize' }}>{e.entity_type}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{e.country_code || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{e.base_currency}</td>
                  <td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{e.tax_id || '—'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: e.is_active ? '#16a34a22' : '#6B728022', color: e.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {e.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 440, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Legal Entity</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Code *', key: 'code' },
                { label: 'Name *', key: 'name' },
                { label: 'Tax ID', key: 'tax_id' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} style={inputStyle} />
                </div>
              ))}
              <div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Entity Type</div>
                <select value={form.entity_type} onChange={e => setForm(p => ({ ...p, entity_type: e.target.value }))} style={inputStyle}>
                  {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Country</div>
                  <input value={form.country_code} onChange={e => setForm(p => ({ ...p, country_code: e.target.value }))} style={inputStyle} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>Base Currency</div>
                  <input value={form.base_currency} onChange={e => setForm(p => ({ ...p, base_currency: e.target.value }))} style={inputStyle} />
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
