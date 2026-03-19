import React, { useState, useEffect, useRef } from 'react'
import { portalApi } from '../api/portal'

interface Props {
  dept: string
  onClose: () => void
}

interface Message {
  role: 'user' | 'agent'
  content: string
  timestamp: Date
}

const PERSONAS: Record<string, string> = {
  management: 'Max',
  finance: 'Fiona',
  sales: 'Sam',
  marketing: 'Maya',
  support: 'Suki',
  hr: 'Hana',
  legal: 'Leo',
  research: 'Rex',
  developer: 'Dev',
  scheduler: 'Sched',
}

const DEPT_COLORS: Record<string, string> = {
  management: '#FF6B8A',
  finance: '#FFB84D',
  sales: '#00D4AA',
  marketing: '#C77DFF',
  support: '#4DA6FF',
  hr: '#DB2777',
  legal: '#F59E0B',
  research: '#4DA6FF',
  developer: '#00D4AA',
  scheduler: '#FFB84D',
}

const GREETINGS: Record<string, string> = {
  management: "Hi, I'm Max. Ready to pull your cross-department KPIs and executive reports.",
  finance: "Hi, I'm Fiona. I can generate financial reports, analyze revenue, or export data.",
  sales: "Hi, I'm Sam. Need help with leads, outreach emails, or pitch decks?",
  marketing: "Hi, I'm Maya. Let's create great marketing content or run campaign analysis.",
  support: "Hi, I'm Suki. I can check tickets, SLA stats, and send customer comms.",
  hr: "Hi, I'm Hana. Ask me about headcount, leave reports, or HR communications.",
  legal: "Hi, I'm Leo. I can review contracts, draft NDAs, or advise on jurisdiction law.",
  research: "Hi, I'm Rex. Give me a topic and I'll research it across the web.",
  developer: "Hi, I'm Dev. Need code written, reviewed, or debugged? I'm on it.",
  scheduler: "Hi, I'm Sched. Tell me what to schedule and I'll sort the cron.",
}

export default function AgentChatDialog({ dept, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)
  const sessionIdRef = useRef<string>(crypto.randomUUID())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const persona = PERSONAS[dept] || dept
  const deptColor = DEPT_COLORS[dept] || '#f97316'
  const agentName = dept.charAt(0).toUpperCase() + dept.slice(1) + ' Agent'

  useEffect(() => {
    const greeting = GREETINGS[dept] || `Hi, I'm ${persona}. How can I help?`
    setMessages([{ role: 'agent', content: greeting, timestamp: new Date() }])
    sessionIdRef.current = crypto.randomUUID()
  }, [dept])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!inputText.trim() || sending) return
    const userMsg = inputText.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }])
    setInputText('')
    setSending(true)
    try {
      const res = await portalApi.sendAgentMessage(dept, userMsg, sessionIdRef.current)
      const data = res.data as Record<string, unknown>
      const reply = (data.reply as string) || (data.message as string) || 'Task received and queued.'
      if (data.session_id) sessionIdRef.current = data.session_id as string
      setMessages(prev => [...prev, { role: 'agent', content: reply, timestamp: new Date() }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: '⚠ Could not reach agent. Please try again.',
        timestamp: new Date(),
      }])
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.65)' }}
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        className="fixed z-50 flex flex-col"
        style={{
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '480px', height: '560px',
          background: '#0F1623',
          border: `1px solid ${deptColor}40`,
          borderRadius: '12px',
          boxShadow: `0 0 40px ${deptColor}20`,
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3 rounded-t-xl"
          style={{ borderBottom: `1px solid ${deptColor}30`, background: `${deptColor}10` }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
              style={{ background: deptColor, color: '#000' }}
            >
              {persona[0]}
            </div>
            <div>
              <div className="text-sm font-semibold text-white">{persona}</div>
              <div className="text-xs" style={{ color: deptColor }}>{agentName}</div>
            </div>
            <div
              className="w-2 h-2 rounded-full ml-1"
              style={{ background: '#00D4AA' }}
              title="Online"
            />
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-lg leading-none px-1"
          >
            ×
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className="max-w-xs px-3 py-2 rounded-xl text-sm leading-relaxed"
                style={msg.role === 'user'
                  ? { background: '#f97316', color: '#fff', borderBottomRightRadius: '4px' }
                  : { background: '#1E2A3A', color: '#E5E7EB', borderBottomLeftRadius: '4px', border: `1px solid ${deptColor}20` }
                }
              >
                {msg.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div
                className="px-3 py-2 rounded-xl text-sm"
                style={{ background: '#1E2A3A', color: '#6B7280' }}
              >
                <span className="animate-pulse">●●●</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-b-xl"
          style={{ borderTop: '1px solid #1E2A3A' }}
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${persona}...`}
            disabled={sending}
            className="flex-1 px-3 py-2 rounded-lg text-sm text-white outline-none"
            style={{
              background: '#1E2A3A',
              border: `1px solid ${inputText ? deptColor + '60' : '#2A3A4A'}`,
              color: '#E5E7EB',
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!inputText.trim() || sending}
            className="px-3 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-40"
            style={{ background: deptColor, color: '#000', minWidth: '60px' }}
          >
            {sending ? '…' : 'Send'}
          </button>
        </div>
      </div>
    </>
  )
}
