import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { portalApi } from '../../api/portal'
import { FinQuote } from '../../types'
import { Send, ArrowRight } from 'lucide-react'

const STATUS_TABS = ['All', 'draft', 'sent', 'accepted', 'declined', 'expired', 'converted']
const STATUS_COLOR: Record<string, string> = {
  draft: '#6B7280',
  sent: '#3b82f6',
  accepted: '#16a34a',
  declined: '#dc2626',
  expired: '#f59e0b',
  converted: '#8b5cf6'
}

export default function SalesQuotesPage() {
  const navigate = useNavigate()
  const [quotes, setQuotes] = useState<FinQuote[]>([])
  const [activeTab, setActiveTab] = useState('All')
  const [entityId, setEntityId] = useState('')
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [converting, setConverting] = useState<string | null>(null)
  const [toast, setToast] = useState('')

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
    portalApi.getQuotes(entityId)
      .then(r => {
        const data: FinQuote[] = r.data?.data || []
        setQuotes(activeTab === 'All' ? data : data.filter(q => q.status === activeTab))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  async function handleConvertToInvoice(q: FinQuote) {
    setConverting(q.id)
    try {
      await portalApi.createInvoice({
        entity_id: entityId,
        customer_id: q.customer_id,
        invoice_date: new Date().toISOString().slice(0, 10),
        due_date: (q as any).expiry_date || new Date().toISOString().slice(0, 10),
        currency: q.currency,
        line_items: (q as any).line_items || [],
        notes: (q as any).notes || '',
        quote_id: q.id,
      })
      setToast('Invoice created successfully')
      setTimeout(() => setToast(''), 4000)
      // refresh quotes
      setLoading(true)
      portalApi.getQuotes(entityId).then(r => {
        const data: FinQuote[] = r.data?.data || []
        setQuotes(activeTab === 'All' ? data : data.filter(q => q.status === activeTab))
      }).finally(() => setLoading(false))
    } catch {
      setToast('Failed to create invoice')
      setTimeout(() => setToast(''), 4000)
    } finally {
      setConverting(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}>Quotes</h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button onClick={() => navigate('/mission-control/sales/quotes/new')}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"
            style={{ background: '#f97316', border: 'none', cursor: 'pointer' }}>
            + New Quote
          </button>
        </div>
      </div>

      {toast && (
        <div className="px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(0,212,170,0.15)', color: '#00D4AA', borderLeft: '3px solid #00D4AA' }}>
          ✓ {toast}
        </div>
      )}

      {/* Status tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #374151' }}>
        {STATUS_TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{
              background: 'none', border: 'none',
              borderBottom: activeTab === tab ? '2px solid #f97316' : '2px solid transparent',
              color: activeTab === tab ? '#f97316' : '#9CA3AF',
              padding: '8px 16px', cursor: 'pointer', fontSize: 13,
              fontWeight: activeTab === tab ? 600 : 400, textTransform: 'capitalize'
            }}>
            {tab}
          </button>
        ))}
      </div>

      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
        ) : quotes.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No quotes found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Quote #', 'Customer', 'Date', 'Expiry', 'Total', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {quotes.map(q => (
                <tr key={q.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{q.quote_number}</td>
                  <td style={{ padding: '10px 14px' }}>{(q as any).customer_name || q.customer_id}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{q.quote_date}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{q.expiry_date || '—'}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{q.currency} {q.total_amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      background: (STATUS_COLOR[q.status] || '#6B7280') + '22',
                      color: STATUS_COLOR[q.status] || '#6B7280',
                      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600
                    }}>
                      {q.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {q.status === 'draft' && (
                      <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#3b82f622', color: '#3b82f6', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                        <Send size={11} /> Send
                      </button>
                    )}
                    {q.status === 'accepted' && (
                      <button
                        onClick={() => handleConvertToInvoice(q)}
                        disabled={converting === q.id}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        <ArrowRight size={11} /> {converting === q.id ? 'Converting...' : 'Invoice'}
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
