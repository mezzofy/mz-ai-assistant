import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../stores/authStore'

// ── Types ──────────────────────────────────────────────────────────────────────

interface WsMessage {
  type: string
  department: string
  status: string
  task_title?: string | null
  agent_task_id?: string | null
}

export interface WsAgentOverride {
  is_busy: boolean
  current_task: string | null
  current_status: string
}

interface UseAgentOfficeWSResult {
  wsOverrides: Record<string, WsAgentOverride>
  wsConnected: boolean
}

// ── Constants ─────────────────────────────────────────────────────────────────

const WS_BASE_URL = 'wss://assistant.mezzofy.com/api/admin-portal/ws'
const MAX_RETRIES = 10
const MAX_BACKOFF_MS = 30_000

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAgentOfficeWS(): UseAgentOfficeWSResult {
  const [wsOverrides, setWsOverrides] = useState<Record<string, WsAgentOverride>>({})
  const [wsConnected, setWsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  useEffect(() => {
    unmountedRef.current = false

    function connect() {
      // Bail out if the component has been unmounted
      if (unmountedRef.current) return

      // Get the JWT token from Zustand auth store (same pattern as client.ts)
      const token = useAuthStore.getState().access_token
      if (!token) {
        // No token yet — do not attempt a WS connection; REST poll is the fallback
        return
      }

      const url = `${WS_BASE_URL}?token=${encodeURIComponent(token)}`

      let ws: WebSocket
      try {
        ws = new WebSocket(url)
      } catch {
        // WebSocket construction failure (e.g. invalid URL in test env) — skip silently
        return
      }

      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) {
          ws.close()
          return
        }
        retryCountRef.current = 0
        setWsConnected(true)
      }

      ws.onmessage = (event: MessageEvent) => {
        if (unmountedRef.current) return
        try {
          const msg: WsMessage = JSON.parse(event.data as string)

          if (!msg.department) return

          setWsOverrides((prev) => {
            const next = { ...prev }
            const dept = msg.department

            if (msg.status === 'queued' || msg.status === 'running') {
              next[dept] = {
                is_busy: true,
                current_task: msg.task_title ?? prev[dept]?.current_task ?? null,
                current_status: msg.status,
              }
            } else if (msg.status === 'completed' || msg.status === 'failed') {
              next[dept] = {
                is_busy: false,
                current_task: null,
                current_status: msg.status,
              }
            }

            return next
          })
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        // onclose will fire after onerror — reconnect logic lives there
      }

      ws.onclose = () => {
        if (unmountedRef.current) return

        setWsConnected(false)
        wsRef.current = null

        if (retryCountRef.current >= MAX_RETRIES) {
          // Exhausted retries — fall back to REST polling silently
          return
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, … capped at 30s
        const delay = Math.min(1_000 * Math.pow(2, retryCountRef.current), MAX_BACKOFF_MS)
        retryCountRef.current += 1

        retryTimerRef.current = setTimeout(() => {
          if (!unmountedRef.current) {
            connect()
          }
        }, delay)
      }
    }

    connect()

    return () => {
      unmountedRef.current = true

      // Cancel any pending reconnect timer
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }

      // Close the WebSocket cleanly
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect loop on intentional close
        wsRef.current.close()
        wsRef.current = null
      }

      setWsConnected(false)
    }
  }, [])

  return { wsOverrides, wsConnected }
}
