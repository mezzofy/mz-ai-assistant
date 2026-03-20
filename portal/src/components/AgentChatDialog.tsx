import React, { useState, useEffect, useRef } from 'react'
import { portalApi } from '../api/portal'
import type { ActiveTask } from '../types'

interface Props {
  dept: string
  onClose: () => void
}

interface Message {
  role: 'user' | 'agent'
  content: string
  timestamp: Date
  isLoading?: boolean
  isBackground?: boolean
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

const POLL_INTERVAL_MS = 4000
const MAX_POLLS = 15 // 15 × 4s = 60s, then background task card

function extractTaskResult(task: ActiveTask): string {
  const r = task.result
  if (!r) return 'Task completed.'
  if (typeof r === 'string') return r
  if (typeof r.response === 'string' && r.response) return r.response
  if (typeof r.reply === 'string' && r.reply) return r.reply
  if (r.artifacts && Array.isArray(r.artifacts) && r.artifacts.length > 0) {
    return `Task completed. ${r.artifacts.length} file(s) generated and saved.`
  }
  if (typeof r.message === 'string' && r.message) return r.message
  return 'Task completed successfully.'
}

export default function AgentChatDialog({ dept, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)
  const sessionIdRef = useRef<string>(crypto.randomUUID())
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollCountRef = useRef<number>(0)
  const backgroundTaskIdRef = useRef<string | null>(null)

  const persona = PERSONAS[dept] || dept
  const deptColor = DEPT_COLORS[dept] || '#f97316'
  const agentName = dept.charAt(0).toUpperCase() + dept.slice(1) + ' Agent'

  const stopPolling = () => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    pollCountRef.current = 0
  }

  useEffect(() => {
    const greeting = GREETINGS[dept] || `Hi, I'm ${persona}. How can I help?`
    setMessages([{ role: 'agent', content: greeting, timestamp: new Date() }])
    sessionIdRef.current = crypto.randomUUID()
    return () => stopPolling()
  }, [dept])

  // Cleanup polling when dialog closes
  useEffect(() => {
    return () => stopPolling()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startPolling = (sessionId: string) => {
    pollCountRef.current = 0
    pollIntervalRef.current = setInterval(async () => {
      pollCountRef.current += 1

      // Background task card after MAX_POLLS (60s)
      if (pollCountRef.current >= MAX_POLLS) {
        stopPolling()
        setSending(false)
        const taskId = backgroundTaskIdRef.current || 'unknown'
        const bgContent =
          `⚙️ Running in background\nTask ID: ${taskId}\nThis task is still running. The agent will update you when it's done.`
        setMessages(prev => {
          const withoutLoading = prev.filter(m => !m.isLoading)
          return [
            ...withoutLoading,
            { role: 'agent', content: bgContent, timestamp: new Date(), isBackground: true },
          ]
        })
        return
      }

      try {
        let task: ActiveTask | undefined

        if (backgroundTaskIdRef.current) {
          // Poll the specific task by ID — more reliable than active list
          const taskRes = await portalApi.getTaskById(backgroundTaskIdRef.current)
          task = taskRes.data as ActiveTask
          if (!task) return
        } else {
          // Fallback: scan active task list when no task ID is available
          const res = await portalApi.getActiveTasks(sessionId)
          const tasks = res.data as ActiveTask[]
          if (!Array.isArray(tasks)) return
          task = tasks.find(t => t.status === 'completed' || t.status === 'failed')
          if (!task) return
        }

        if (task.status === 'completed' || task.status === 'failed') {
          stopPolling()
          setSending(false)

          if (task.status === 'failed') {
            const errMsg = task.error || 'Agent encountered an error. Please try again.'
            setMessages(prev => {
              const withoutLoading = prev.filter(m => !m.isLoading)
              return [...withoutLoading, { role: 'agent', content: `⚠ ${errMsg}`, timestamp: new Date() }]
            })
          } else {
            const result = extractTaskResult(task)
            setMessages(prev => {
              const withoutLoading = prev.filter(m => !m.isLoading)
              return [...withoutLoading, { role: 'agent', content: result, timestamp: new Date() }]
            })
          }
        }
        // If still queued/running — keep polling (loading bubble stays)
      } catch {
        // Ignore transient poll errors — keep polling until timeout
      }
    }, POLL_INTERVAL_MS)
  }

  const sendMessage = async () => {
    if (!inputText.trim() || sending) return
    const userMsg = inputText.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }])
    setInputText('')
    setSending(true)
    try {
      const res = await portalApi.sendAgentMessage(dept, userMsg, sessionIdRef.current)
      const data = res.data as Record<string, unknown>

      // Update session_id if server returns one
      if (data.session_id) sessionIdRef.current = data.session_id as string

      const isQueued =
        data.status === 'queued' || data.status === 'pending'

      if (isQueued) {
        // Capture task_id for the background task card
        backgroundTaskIdRef.current = (data.task_id as string) || null
        // Add loading bubble and start polling
        setMessages(prev => [
          ...prev,
          {
            role: 'agent',
            content: 'Working on it...',
            timestamp: new Date(),
            isLoading: true,
          },
        ])
        startPolling(sessionIdRef.current)
      } else {
        // Sync response — display immediately
        const reply =
          (data.reply as string) ||
          (data.response as string) ||
          (data.message as string) ||
          'Done.'
        setMessages(prev => [...prev, { role: 'agent', content: reply, timestamp: new Date() }])
        setSending(false)
      }
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: 'agent',
          content: '⚠ Could not reach agent. Please try again.',
          timestamp: new Date(),
        },
      ])
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
                  : msg.isBackground
                    ? {
                        background: '#1A2535',
                        color: '#94A3B8',
                        borderBottomLeftRadius: '4px',
                        border: '1px solid #334155',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'inherit',
                      }
                    : msg.isLoading
                      ? {
                          background: '#1E2A3A',
                          color: '#6B7280',
                          borderBottomLeftRadius: '4px',
                          border: `1px solid ${deptColor}20`,
                          fontStyle: 'italic',
                        }
                      : { background: '#1E2A3A', color: '#E5E7EB', borderBottomLeftRadius: '4px', border: `1px solid ${deptColor}20` }
                }
              >
                {msg.isLoading ? (
                  <span>
                    <span className="animate-pulse">⏳</span>
                    {' '}{msg.content}
                  </span>
                ) : msg.isBackground ? (
                  <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          {sending && !messages.some(m => m.isLoading) && (
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
