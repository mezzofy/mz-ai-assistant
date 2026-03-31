import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { FinanceDashboardData, FinEntity } from '../../types'

const KpiCard = ({ title, value, currency = 'SGD', color = '#f97316' }: any) => (
  <div style={{ background: '#1F2937', borderRadius: 8, padding: '20px', flex: 1, minWidth: 180, border: '1px solid #1E3A5F' }}>
    <div style={{ color: '#9CA3AF', fontSize: 13, marginBottom: 8 }}>{title}</div>
    <div style={{ color, fontSize: 22, fontWeight: 700 }}>
      {currency} {typeof value === 'number' ? value.toLocaleString('en-SG', { minimumFractionDigits: 2 }) : '0.00'}
    </div>
  </div>
)

const statusColors: Record<string, string> = {
  draft: '#6B7280', posted: '#16a34a', reversed: '#dc2626',
  sent: '#3b82f6', partial: '#f59e0b', paid: '#16a34a', overdue: '#dc2626'
}

export default function FinanceDashboard() {
  const navigate = useNavigate()
  const [entities, setEntities] = useState<FinEntity[]>([])
  const [selectedEntity, setSelectedEntity] = useState<string>('')
  const [dashboard, setDashboard] = useState<FinanceDashboardData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setSelectedEntity(ents[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedEntity) return
    setLoading(true)
    portalApi.getFinanceDashboard(selectedEntity)
      .then(r => setDashboard(r.data?.data || null))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [selectedEntity])

  const kpis = dashboard?.kpis
  const pnl = dashboard?.pnl_mtd
  const recentJEs = dashboard?.recent_journal_entries || []

  return (
    <div style={{ padding: '24px', color: '#F9FAFB' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Finance</h1>
          <p style={{ color: '#6B7280', fontSize: 13, margin: '4px 0 0' }}>Financial operations & reporting</p>
        </div>
        <select
          value={selectedEntity}
          onChange={e => setSelectedEntity(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}
        >
          <option value="">Select Entity</option>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <KpiCard title="AR Outstanding" value={kpis?.ar_outstanding} color="#f97316" />
        <KpiCard title="AP Outstanding" value={kpis?.ap_outstanding} color="#dc2626" />
        <KpiCard title="Cash Balance" value={kpis?.cash_balance} color="#16a34a" />
        <KpiCard title="Net P&L MTD" value={pnl?.net_profit} color={(pnl?.net_profit ?? 0) >= 0 ? '#16a34a' : '#dc2626'} />
      </div>

      {/* Quick Actions */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        {[
          { label: '+ Invoice', path: '/mission-control/finance/invoices' },
          { label: '+ Bill', path: '/mission-control/finance/bills' },
          { label: '+ Journal', path: '/mission-control/finance/journal' },
          { label: 'Reports', path: '/mission-control/finance/reports' },
        ].map(btn => (
          <button key={btn.label} onClick={() => navigate(btn.path)}
            style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
            {btn.label}
          </button>
        ))}
      </div>

      {/* Recent Journal Entries */}
      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #1E3A5F' }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Recent Journal Entries</h3>
        </div>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : recentJEs.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#6B7280' }}>No journal entries yet</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Entry #', 'Date', 'Description', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentJEs.map((je: any, i: number) => (
                <tr key={je.entry_number || i} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 16px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{je.entry_number}</td>
                  <td style={{ padding: '10px 16px', color: '#9CA3AF' }}>{je.entry_date}</td>
                  <td style={{ padding: '10px 16px' }}>{je.description}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ background: (statusColors[je.status] || '#6B7280') + '22', color: statusColors[je.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {je.status?.toUpperCase()}
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
