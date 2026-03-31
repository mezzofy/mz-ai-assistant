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

  return (
    <div style={{ padding: 24, color: '#F9FAFB' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Bills</h1>
        <select value={entityId} onChange={e => setEntityId(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
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
    </div>
  )
}
