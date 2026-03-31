import React, { useState, useEffect } from 'react'
import { portalApi } from '../../api/portal'
import { JournalEntry } from '../../types'

const STATUS_TABS = ['All', 'draft', 'posted', 'reversed']
const STATUS_COLOR: Record<string, string> = {
  draft: '#6B7280', posted: '#16a34a', reversed: '#dc2626'
}

export default function JournalEntries() {
  const [entries, setEntries] = useState<JournalEntry[]>([])
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
    portalApi.getJournalEntries(entityId, status)
      .then(r => setEntries(r.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [entityId, activeTab])

  const handlePost = async (id: string) => {
    await portalApi.postJournalEntry(id)
    setEntries(prev => prev.map(e => e.id === id ? { ...e, status: 'posted' as const } : e))
  }

  const handleReverse = async (id: string) => {
    if (!confirm('Reverse this journal entry?')) return
    await portalApi.reverseJournalEntry(id)
    setEntries(prev => prev.map(e => e.id === id ? { ...e, status: 'reversed' as const } : e))
  }

  return (
    <div style={{ padding: 24, color: '#F9FAFB' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Journal Entries</h1>
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
        ) : entries.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>No journal entries found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#374151' }}>
                {['Entry #', 'Date', 'Description', 'Currency', 'Reference', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9CA3AF', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(je => (
                <tr key={je.id} style={{ borderTop: '1px solid #374151' }}>
                  <td style={{ padding: '10px 14px', color: '#f97316', fontFamily: 'monospace', fontSize: 12 }}>{je.entry_number}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{je.entry_date}</td>
                  <td style={{ padding: '10px 14px' }}>{je.description}</td>
                  <td style={{ padding: '10px 14px', color: '#9CA3AF' }}>{je.currency}</td>
                  <td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{je.reference || '—'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: (STATUS_COLOR[je.status] || '#6B7280') + '22', color: STATUS_COLOR[je.status] || '#6B7280', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {je.status?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {je.status === 'draft' && (
                      <button onClick={() => handlePost(je.id)}
                        style={{ background: '#16a34a22', color: '#16a34a', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6 }}>
                        Post
                      </button>
                    )}
                    {je.status === 'posted' && (
                      <button onClick={() => handleReverse(je.id)}
                        style={{ background: '#dc262622', color: '#dc2626', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 12 }}>
                        Reverse
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
