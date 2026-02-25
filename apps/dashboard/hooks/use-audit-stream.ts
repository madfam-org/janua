'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { januaClient } from '@/lib/janua-client'
import { listAuditLogs, type AuditLog } from '@/lib/api'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'polling'

interface UseAuditStreamOptions {
  maxEvents?: number
  autoConnect?: boolean
  pollInterval?: number
}

interface UseAuditStreamReturn {
  events: AuditLog[]
  status: ConnectionStatus
  isPaused: boolean
  connect: () => void
  disconnect: () => void
  pause: () => void
  resume: () => void
  clear: () => void
}

export function useAuditStream(options: UseAuditStreamOptions = {}): UseAuditStreamReturn {
  const { maxEvents = 100, autoConnect = true, pollInterval = 5000 } = options

  const [events, setEvents] = useState<AuditLog[]>([])
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [isPaused, setIsPaused] = useState(false)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)
  const lastEventIdRef = useRef<string | null>(null)
  const wsConnectedRef = useRef(false)

  const addEvent = useCallback(
    (event: AuditLog) => {
      setEvents((prev) => {
        if (prev.some((e) => e.id === event.id)) return prev
        const updated = [event, ...prev]
        return updated.slice(0, maxEvents)
      })
    },
    [maxEvents]
  )

  const connectWebSocket = useCallback(() => {
    if (!januaClient.ws) {
      // No WebSocket configured — fall back to polling
      startPolling()
      return
    }

    setStatus('connecting')

    const ws = januaClient.ws

    const onConnected = () => {
      wsConnectedRef.current = true
      setStatus('connected')
      ws.subscribe('audit')
    }

    const onMessage = (msg: { type: string; channel?: string; data?: unknown }) => {
      if (msg.channel === 'audit' && msg.data && !isPaused) {
        addEvent(msg.data as AuditLog)
      }
    }

    const onDisconnected = () => {
      wsConnectedRef.current = false
      setStatus('disconnected')
      // Fall back to polling
      startPolling()
    }

    const onError = () => {
      setStatus('error')
      // Fall back to polling
      startPolling()
    }

    ws.on('connected', onConnected)
    ws.on('message', onMessage)
    ws.on('disconnected', onDisconnected)
    ws.on('error', onError)

    if (ws.isConnected()) {
      onConnected()
    } else {
      ws.connect().catch(() => {
        // Connection failed — fall back to polling
        startPolling()
      })
    }

    return () => {
      ws.off('connected', onConnected)
      ws.off('message', onMessage)
      ws.off('disconnected', onDisconnected)
      ws.off('error', onError)
      if (wsConnectedRef.current) {
        ws.unsubscribe('audit')
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addEvent, isPaused])

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return // Already polling

    setStatus('polling')

    const poll = async () => {
      if (isPaused) return
      try {
        const params: Record<string, string> = { limit: '20' }
        const logs = await listAuditLogs(params)
        if (Array.isArray(logs)) {
          for (const log of logs) {
            if (!lastEventIdRef.current || log.id !== lastEventIdRef.current) {
              addEvent(log)
            }
          }
          if (logs.length > 0) {
            lastEventIdRef.current = logs[0].id
          }
        }
      } catch {
        // Silently retry on next interval
      }
    }

    poll()
    pollTimerRef.current = setInterval(poll, pollInterval)
  }, [addEvent, isPaused, pollInterval])

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    connectWebSocket()
  }, [connectWebSocket])

  const disconnect = useCallback(() => {
    stopPolling()
    if (januaClient.ws && wsConnectedRef.current) {
      januaClient.ws.unsubscribe('audit')
    }
    wsConnectedRef.current = false
    setStatus('disconnected')
  }, [stopPolling])

  const pause = useCallback(() => setIsPaused(true), [])
  const resume = useCallback(() => setIsPaused(false), [])
  const clear = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (autoConnect) {
      const cleanup = connectWebSocket()
      return () => {
        cleanup?.()
        stopPolling()
      }
    }
    return () => stopPolling()
  }, [autoConnect, connectWebSocket, stopPolling])

  return { events, status, isPaused, connect, disconnect, pause, resume, clear }
}
