import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinBill } from '../../types'

const STATUS_TABS = ['All', 'pending', 'approved', 'partial', 'paid']
const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b', approved: '#3b82f6', partial: '#f97316',
  paid: '#16a34a', cancelled: '#6B7280'
}

export default function Bills() {
  const [bills, setBills] = useState<FinBill[]>([])
  const [activeTab, setActiveTab] = useState('All')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [newForm, setNewForm] = useState({ vendor_name: '', bill_date: new Date().toISOString().slice(0,10), due_date: '', reference: '', currency: 'SGD', notes: '' })
  const [creating, setCreating] = useState(false)

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
    const status = activeTab === 'All' ? undefined : activeTab
    portalApi.getBills(entityId, status)
      .then(r => setBills(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  const handleApprove = async (id: string) => {
    // Approve by creating a payment or updating status via a bill approve endpoint
    setBills(prev => prev.map(b => b.id === id ? { ...b, status: 'approved' as const } : b))
  }

  const currency = entities.find(e => e.id === entityId)?.base_currency || 'SGD'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Bills</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => setShowNewModal(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Bill
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #374151' }}>
        {STATUS_TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{ background: 'none', border: 'none', borderBottom: activeTab === tab ? '2px solid #f97316' : '2px solid transparent', color: activeTab === tab ? '#f97316' : '#9CA3AF', padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: activeTab === tab ? 600 : 400, textTransform: 'capitalize' }}>
            {tab}
          </button>
        ))}
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : bills.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No bills found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Bill #', 'Vendor', 'Date', 'Due', 'Total', 'Outstanding', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bills.map(bill => (
                <tr key={bill.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{bill.bill_number}</td>
                  <td style={{ padding: '10px 14px' }}>{(bill as any).vendor_name || bill.vendor_id}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{bill.bill_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{bill.due_date}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{bill.currency} {bill.total_amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px', color: bill.outstanding > 0 ? '#f59e0b' : '#16a34a' }}>
                    {bill.currency} {bill.outstanding?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[bill.status] || '#6B7280') + '22', color: STATUS_COLOR[bill.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {bill.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {bill.status === 'pending' && (
                      <button onClick={() => handleApprove(bill.id)}
                        style={{ background: '#3b82f622', color: '#3b82f6', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        Approve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {showNewModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#1F2937', borderRadius: 10, padding: 28, width: 480, border: '1px solid #374151' }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>New Bill</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Vendor Name *', key: 'vendor_name', type: 'text' },
                { label: 'Bill Date *', key: 'bill_date', type: 'date' },
                { label: 'Due Date *', key: 'due_date', type: 'date' },
                { label: 'Reference', key: 'reference', type: 'text' },
                { label: 'Currency', key: 'currency', type: 'text' },
                { label: 'Notes', key: 'notes', type: 'text' },
              ].map(f => (
                <div key={f.key}>
                  <div style={{ color: '#9CA3AF', fontSize: 12, marginBottom: 4 }}>{f.label}</div>
                  <input type={f.type} value={(newForm as any)[f.key]} onChange={e => setNewForm(p => ({ ...p, [f.key]: e.target.value }))}
                    style={{ background: '#111827', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '8px 12px', fontSize: 13, width: '100%', boxSizing: 'border-box' as const }} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewModal(false)} style={{ background: '#374151', color: '#F9FAFB', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Cancel</button>
              <button onClick={async () => {
                setCreating(true)
                try {
                  await portalApi.createBill({ entity_id: entityId, ...newForm, line_items: [] })
                  setShowNewModal(false)
                  setNewForm({ vendor_name: '', bill_date: new Date().toISOString().slice(0,10), due_date: '', reference: '', currency: currency, notes: '' })
                  setLoading(true)
                  portalApi.getBills(entityId, activeTab === 'All' ? undefined : activeTab).then(r => setBills(r.data?.data || [])).finally(() => setLoading(false))
                } catch { /* ignore */ } finally { setCreating(false) }
              }} disabled={creating} className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all" style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
                {creating ? 'Creating...' : 'Create Bill'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
