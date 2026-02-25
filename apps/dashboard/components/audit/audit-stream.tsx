'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import {
  Wifi,
  WifiOff,
  Pause,
  Play,
  Trash2,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { useAuditStream, type ConnectionStatus } from '@/hooks/use-audit-stream'
import type { AuditLog } from '@/lib/api'

const STATUS_CONFIG: Record<ConnectionStatus, { label: string; color: string; icon: typeof Wifi }> = {
  connecting: { label: 'Connecting...', color: 'bg-yellow-500', icon: Loader2 },
  connected: { label: 'Live', color: 'bg-green-500', icon: Wifi },
  disconnected: { label: 'Disconnected', color: 'bg-gray-500', icon: WifiOff },
  error: { label: 'Error', color: 'bg-red-500', icon: WifiOff },
  polling: { label: 'Polling', color: 'bg-blue-500', icon: RefreshCw },
}

interface EventFilterState {
  types: Set<string>
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return iso
  }
}

function getActionColor(action: string): string {
  if (action.includes('delete') || action.includes('ban') || action.includes('revoke')) {
    return 'text-red-600 dark:text-red-400'
  }
  if (action.includes('create') || action.includes('register') || action.includes('login')) {
    return 'text-green-600 dark:text-green-400'
  }
  if (action.includes('update') || action.includes('change')) {
    return 'text-blue-600 dark:text-blue-400'
  }
  return 'text-muted-foreground'
}

export function AuditStream() {
  const { events, status, isPaused, connect, disconnect, pause, resume, clear } = useAuditStream()
  const [filters, setFilters] = useState<EventFilterState>({ types: new Set() })

  const statusConfig = STATUS_CONFIG[status]
  const StatusIcon = statusConfig.icon

  const filteredEvents = filters.types.size > 0
    ? events.filter((e) => filters.types.has(e.action))
    : events

  const uniqueActions = Array.from(new Set(events.map((e) => e.action)))

  const toggleFilter = (action: string) => {
    setFilters((prev) => {
      const next = new Set(prev.types)
      if (next.has(action)) {
        next.delete(action)
      } else {
        next.add(action)
      }
      return { types: next }
    })
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-base">Live Audit Feed</CardTitle>
            <div className="flex items-center gap-1.5">
              <span className={`inline-block size-2 rounded-full ${statusConfig.color} ${status === 'connected' ? 'animate-pulse' : ''}`} />
              <span className="text-muted-foreground text-xs">{statusConfig.label}</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {status === 'disconnected' ? (
              <Button variant="ghost" size="sm" onClick={connect} className="h-7 gap-1 text-xs">
                <Wifi className="size-3" />
                Connect
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={disconnect} className="h-7 gap-1 text-xs">
                <WifiOff className="size-3" />
                Stop
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={isPaused ? resume : pause}
              className="h-7 gap-1 text-xs"
              disabled={status === 'disconnected'}
            >
              {isPaused ? <Play className="size-3" /> : <Pause className="size-3" />}
              {isPaused ? 'Resume' : 'Pause'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clear}
              className="h-7 gap-1 text-xs"
              disabled={events.length === 0}
            >
              <Trash2 className="size-3" />
              Clear
            </Button>
          </div>
        </div>

        {uniqueActions.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-2">
            {uniqueActions.map((action) => (
              <Badge
                key={action}
                variant={filters.types.has(action) ? 'default' : 'outline'}
                className="cursor-pointer text-xs"
                onClick={() => toggleFilter(action)}
              >
                {action}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>

      <CardContent>
        {filteredEvents.length === 0 ? (
          <div className="text-muted-foreground flex flex-col items-center justify-center py-8 text-sm">
            <StatusIcon className={`mb-2 size-8 ${status === 'connecting' ? 'animate-spin' : ''}`} />
            <p>{status === 'disconnected' ? 'Click Connect to start streaming' : 'Waiting for events...'}</p>
          </div>
        ) : (
          <div className="max-h-96 space-y-1 overflow-y-auto">
            {filteredEvents.map((event) => (
              <AuditEventRow key={event.id} event={event} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AuditEventRow({ event }: { event: AuditLog }) {
  return (
    <div className="hover:bg-muted/50 flex items-center gap-3 rounded px-2 py-1.5 text-sm transition-colors">
      <span className="text-muted-foreground w-20 shrink-0 font-mono text-xs">
        {formatTime(event.created_at)}
      </span>
      <span className={`w-32 shrink-0 truncate font-medium ${getActionColor(event.action)}`}>
        {event.action}
      </span>
      <span className="text-muted-foreground truncate text-xs">
        {event.user_email || event.user_id || 'system'}
      </span>
      {event.ip_address && (
        <span className="text-muted-foreground ml-auto shrink-0 font-mono text-xs">
          {event.ip_address}
        </span>
      )}
    </div>
  )
}
