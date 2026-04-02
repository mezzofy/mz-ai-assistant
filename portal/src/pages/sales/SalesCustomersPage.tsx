import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { FinCustomer } from '../../types'

export default function SalesCustomersPage() {
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<FinCustomer[]>([])
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
    portalApi.getFinanceCustomers(entityId)
      .then(r => setCustomers(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])


  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Customers</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => navigate('/mission-control/sales/customers/new')}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Customer
          </button>
        </div>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : customers.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No customers found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Code', 'Name', 'Type', 'Industry', 'Location', 'Currency', 'Terms', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {customers.map(c => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/mission-control/sales/customers/${c.id}`)}
                  className="cursor-pointer hover:bg-white/5 transition-colors"
                  style={{ borderTop: '1px solid #374151' }}
                >
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{c.customer_code}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 500 }}>{c.name}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF', textTransform: 'capitalize' }}>{(c as any).customer_type || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{(c as any).industry || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{(c as any).location || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{c.currency}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{c.payment_terms}d</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: c.is_active ? '#16a34a22' : '#6B728022', color: c.is_active ? '#16a34a' : '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {c.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
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
