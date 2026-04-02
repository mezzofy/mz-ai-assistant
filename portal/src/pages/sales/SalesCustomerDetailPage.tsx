import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { portalApi } from '../../api/portal'

const TABS = ['Profile', 'Payment', 'Quotes', 'Invoices'] as const
type Tab = typeof TABS[number]

export default function SalesCustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('Profile')
  const [customer, setCustomer] = useState<any>(null)
  const [entities, setEntities] = useState<any[]>([])
  const [entityId, setEntityId] = useState('')
  const [quotes, setQuotes] = useState<any[]>([])
  const [invoices, setInvoices] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [converting, setConverting] = useState<string | null>(null)
  const [toast, setToast] = useState('')

  useEffect(() => {
    portalApi.getFinanceEntities().then(r => {
      const ents = r.data?.data || []
      setEntities(ents)
      if (ents.length > 0) setEntityId(ents[0].id)
    })
  }, [])

  useEffect(() => {
    if (!entityId || !id) return
    setLoading(true)
    Promise.all([
      portalApi.getFinanceCustomers(entityId),
      portalApi.getQuotes(entityId),
      portalApi.getInvoices(entityId),
    ]).then(([custRes, quotesRes, invRes]) => {
      const custs = custRes.data?.data || []
      setCustomer(custs.find((c: any) => c.id === id) || null)
      const allQuotes = quotesRes.data?.data || []
      setQuotes(allQuotes.filter((q: any) => q.customer_id === id))
      const allInvs = invRes.data?.data || []
      setInvoices(allInvs.filter((inv: any) => inv.customer_id === id))
    }).finally(() => setLoading(false))
  }, [entityId, id])

  async function handleConvertToInvoice(quote: any) {
    setConverting(quote.id)
    try {
      await portalApi.createInvoice({
        entity_id: entityId,
        customer_id: quote.customer_id,
        invoice_date: new Date().toISOString().slice(0, 10),
        due_date: quote.expiry_date || new Date().toISOString().slice(0, 10),
        currency: quote.currency,
        line_items: quote.line_items || [],
        notes: quote.notes || '',
        quote_id: quote.id,
      })
      setToast('Invoice created successfully')
      setTimeout(() => setToast(''), 4000)
      // Refresh invoices
      const invRes = await portalApi.getInvoices(entityId)
      const allInvs = invRes.data?.data || []
      setInvoices(allInvs.filter((inv: any) => inv.customer_id === id))
      setTab('Invoices')
    } catch {
      setToast('Failed to create invoice')
      setTimeout(() => setToast(''), 4000)
    } finally {
      setConverting(null)
    }
  }

  const STATUS_COLOR: Record<string, string> = {
    draft: '#6B7280', sent: '#3b82f6', accepted: '#16a34a',
    declined: '#dc2626', expired: '#f59e0b', converted: '#8b5cf6'
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Loading...</div>
  if (!customer) return <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>Customer not found</div>

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/mission-control/sales/customers')}
          className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={16} /> Customers
        </button>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {customer.name}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-sm font-mono" style={{ color: '#f97316' }}>{customer.customer_code}</span>
            <span className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: customer.is_active ? '#16a34a22' : '#6B728022', color: customer.is_active ? '#16a34a' : '#9CA3AF' }}>
              {customer.is_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
        </div>
        <select value={entityId} onChange={e => setEntityId(e.target.value)}
          style={{ background: '#1F2937', color: '#F9FAFB', border: '1px solid #374151', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
          {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>

      {toast && (
        <div className="px-4 py-2 rounded-lg text-sm"
          style={{ background: 'rgba(0,212,170,0.15)', color: '#00D4AA', borderLeft: '3px solid #00D4AA' }}>
          ✓ {toast}
        </div>
      )}

      {/* Tabs */}
      <div style={{ borderBottom: '1px solid #374151', display: 'flex', gap: 4 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              background: 'none', border: 'none',
              borderBottom: tab === t ? '2px solid #f97316' : '2px solid transparent',
              color: tab === t ? '#f97316' : '#9CA3AF',
              padding: '8px 16px', cursor: 'pointer', fontSize: 13,
              fontWeight: tab === t ? 600 : 400,
            }}>
            {t}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #1E3A5F', padding: 24 }}>
        {tab === 'Profile' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {[
              ['Name', customer.name],
              ['Company', customer.company_name || '—'],
              ['Email', customer.email || '—'],
              ['Phone', customer.phone || '—'],
              ['Industry', customer.industry || '—'],
              ['Location', customer.location || '—'],
              ['Account Manager', customer.account_manager || '—'],
              ['Type', customer.customer_type || '—'],
            ].map(([label, value]) => (
              <div key={label}>
                <div style={{ color: '#6B7280', fontSize: 12, marginBottom: 4 }}>{label}</div>
                <div style={{ color: '#F9FAFB', fontSize: 14 }}>{value}</div>
              </div>
            ))}
          </div>
        )}

        {tab === 'Payment' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {[
              ['Currency', customer.currency || '—'],
              ['Payment Terms', customer.payment_terms ? `${customer.payment_terms} days` : '—'],
            ].map(([label, value]) => (
              <div key={label}>
                <div style={{ color: '#6B7280', fontSize: 12, marginBottom: 4 }}>{label}</div>
                <div style={{ color: '#F9FAFB', fontSize: 14 }}>{value}</div>
              </div>
            ))}
          </div>
        )}

        {tab === 'Quotes' && (
          quotes.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#6B7280', padding: 40 }}>No quotes for this customer</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Quote #', 'Date', 'Expiry', 'Total', 'Status', 'Action'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500, borderBottom: '1px solid #374151' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {quotes.map(q => (
                  <tr key={q.id} style={{ borderBottom: '1px solid #374151' }}>
                    <td style={{ padding: '10px 12px', color: '#f97316', fontFamily: 'monospace' }}>{q.quote_number}</td>
                    <td style={{ padding: '10px 12px', color: '#9CA3AF' }}>{q.quote_date}</td>
                    <td style={{ padding: '10px 12px', color: '#9CA3AF' }}>{q.expiry_date || '—'}</td>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>{q.currency} {q.total_amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ background: (STATUS_COLOR[q.status] || '#6B7280') + '22', color: STATUS_COLOR[q.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                        {q.status?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {(q.status === 'accepted' || q.status === 'draft') && (
                        <button onClick={() => handleConvertToInvoice(q)} disabled={converting === q.id}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                          <ArrowRight size={11} /> {converting === q.id ? 'Converting...' : 'Convert to Invoice'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}

        {tab === 'Invoices' && (
          invoices.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#6B7280', padding: 40 }}>No invoices for this customer</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Invoice #', 'Date', 'Due', 'Total', 'Status'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500, borderBottom: '1px solid #374151' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} style={{ borderBottom: '1px solid #374151' }}>
                    <td style={{ padding: '10px 12px', color: '#f97316', fontFamily: 'monospace' }}>{inv.invoice_number}</td>
                    <td style={{ padding: '10px 12px', color: '#9CA3AF' }}>{inv.invoice_date}</td>
                    <td style={{ padding: '10px 12px', color: '#9CA3AF' }}>{inv.due_date || '—'}</td>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>{inv.currency} {inv.total_amount?.toLocaleString('en-SG', { minimumFractionDigits: 2 })}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ background: '#374151', color: '#9CA3AF', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                        {inv.status?.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  )
}
