import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { FinPayment } from '../../types'

const TYPE_COLOR: Record<string, string> = {
  receipt: '#16a34a',
  payment: '#f97316'
}

export default function Payments() {
  const navigate = useNavigate()
  const [payments, setPayments] = useState<FinPayment[]>([])
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
    portalApi.getPayments(entityId)
      .then(r => setPayments(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Payments</h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => navigate('/mission-control/finance/payments/new')}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Payment
          </button>
        </div>
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : payments.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No payments found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Payment #', 'Type', 'Date', 'Amount', 'Method', 'Reference'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{p.payment_number}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (TYPE_COLOR[p.payment_type] || '#6B7280') + '22', color: TYPE_COLOR[p.payment_type] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {p.payment_type?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.payment_date}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{p.currency} {p.amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{p.payment_method || '—'}</td>
                  <td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{p.reference || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
