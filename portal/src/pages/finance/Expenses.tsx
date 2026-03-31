import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { FinExpense } from '../../types'

const STATUS_TABS = ['All', 'pending', 'approved', 'rejected', 'reimbursed']
const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b', approved: '#16a34a', rejected: '#dc2626', reimbursed: '#3b82f6'
}

export default function Expenses() {
  const [expenses, setExpenses] = useState<FinExpense[]>([])
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
    portalApi.getExpenses(entityId, status)
      .then(r => setExpenses(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    await portalApi.approveExpense(id, action)
    setExpenses(prev => prev.map(e => e.id === id ? { ...e, status: (action === 'approve' ? 'approved' : 'rejected') as FinExpense['status'] } : e))
  }

  return (
    <div style={{ padding: 24, color: '#F9FAFB' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Expenses</h1>
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
        ) : expenses.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No expenses found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Expense #', 'Date', 'Category', 'Description', 'Amount', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {expenses.map(exp => (
                <tr key={exp.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{exp.expense_number}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{exp.expense_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{exp.category}</td>
                  <td style={{ padding: '10px 14px' }}>{exp.description}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{exp.currency} {exp.amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[exp.status] || '#6B7280') + '22', color: STATUS_COLOR[exp.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {exp.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {exp.status === 'pending' && (
                      <>
                        <button onClick={() => handleAction(exp.id, 'approve')}
                          style={{ background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                          Approve
                        </button>
                        <button onClick={() => handleAction(exp.id, 'reject')}
                          style={{ background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                          Reject
                        </button>
                      </>
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
