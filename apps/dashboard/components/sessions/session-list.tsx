'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button, Badge } from '@janua/ui'
import {
  MoreHorizontal,
  Search,
  Shield,
  Globe,
  Smartphone,
  Tablet,
  Monitor,
  Loader2,
  AlertCircle,
  RefreshCw,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@janua/ui'
import { Input } from '@janua/ui'
import { januaClient } from '@/lib/janua-client'

interface Session {
  id: string
  user_id?: string
  user_email?: string
  device_type?: string
  browser?: string
  os?: string
  ip_address: string
  location?: {
    city?: string
    country?: string
  }
  user_agent?: string
  created_at: string
  last_active_at?: string
  expires_at?: string
  is_current?: boolean
  status?: 'active' | 'expired' | 'revoked'
}

export function SessionList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [revokingAll, setRevokingAll] = useState(false)

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const data = await januaClient.sessions.listSessions()
      const sessionList = (data as any).items || data || []

      // Normalize session data
      const normalized: Session[] = sessionList.map((s: any) => ({
        id: s.id,
        user_id: s.user_id,
        user_email: s.user_email,
        device_type: s.device_type || s.device?.type || parseDeviceType(s.user_agent),
        browser: s.browser || s.device?.browser || parseBrowser(s.user_agent),
        os: s.os || s.device?.os || parseOS(s.user_agent),
        ip_address: s.ip_address || s.ip || 'Unknown',
        location: s.location,
        user_agent: s.user_agent,
        created_at: s.created_at,
        last_active_at: s.last_active_at || s.lastActiveAt || s.created_at,
        expires_at: s.expires_at,
        is_current: s.is_current || s.isCurrent || false,
        status: s.status || 'active',
      }))

      setSessions(normalized)
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
      setError(err instanceof Error ? err.message : 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const revokeSession = async (sessionId: string) => {
    try {
      setRevokingId(sessionId)
      await januaClient.sessions.revokeSession(sessionId)
      await fetchSessions()
    } catch (err) {
      console.error('Failed to revoke session:', err)
    } finally {
      setRevokingId(null)
    }
  }

  const revokeAllSessions = async () => {
    try {
      setRevokingAll(true)
      await januaClient.sessions.revokeAllSessions()
      await fetchSessions()
    } catch (err) {
      console.error('Failed to revoke all sessions:', err)
    } finally {
      setRevokingAll(false)
    }
  }

  const filteredSessions = sessions.filter((session) => {
    if (!searchTerm) return true
    const search = searchTerm.toLowerCase()
    return (
      (session.user_email?.toLowerCase().includes(search)) ||
      (session.ip_address?.toLowerCase().includes(search)) ||
      (session.browser?.toLowerCase().includes(search)) ||
      (session.os?.toLowerCase().includes(search))
    )
  })

  const activeSessions = sessions.filter((s) => s.status === 'active' || !s.status).length

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading sessions...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Sessions</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchSessions} variant="outline">
          <RefreshCw className="mr-2 size-4" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Stats Banner */}
      <div className="bg-muted/50 grid grid-cols-2 gap-4 rounded-lg p-4">
        <div>
          <div className="text-2xl font-bold">{activeSessions}</div>
          <div className="text-muted-foreground text-sm">Active Sessions</div>
        </div>
        <div>
          <div className="text-2xl font-bold">{sessions.length}</div>
          <div className="text-muted-foreground text-sm">Total Sessions</div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
          <Input
            placeholder="Search sessions by email, IP, browser..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={fetchSessions} disabled={loading}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={revokeAllSessions}
            disabled={revokingAll || sessions.length === 0}
          >
            {revokingAll ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 size-4" />
            )}
            Revoke All Others
          </Button>
        </div>
      </div>

      {/* Session Table */}
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/50 border-b">
              <th className="p-4 text-left text-sm font-medium">Device & Browser</th>
              <th className="p-4 text-left text-sm font-medium">IP Address</th>
              <th className="p-4 text-left text-sm font-medium">Location</th>
              <th className="p-4 text-left text-sm font-medium">Status</th>
              <th className="p-4 text-left text-sm font-medium">Last Activity</th>
              <th className="p-4 text-left text-sm font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {filteredSessions.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground p-8 text-center">
                  {searchTerm ? 'No sessions match your search' : 'No active sessions'}
                </td>
              </tr>
            ) : (
              filteredSessions.map((session) => (
                <tr key={session.id} className="hover:bg-muted/50 border-b">
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <DeviceIcon type={session.device_type} />
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium">
                          {session.browser || 'Unknown'} on {session.os || session.device_type || 'Unknown'}
                          {session.is_current && (
                            <Badge variant="secondary" className="text-xs">Current</Badge>
                          )}
                        </div>
                        {session.user_email && (
                          <div className="text-muted-foreground text-xs">{session.user_email}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className="font-mono text-sm">{session.ip_address}</span>
                  </td>
                  <td className="p-4">
                    <span className="text-muted-foreground text-sm">
                      {session.location?.city && session.location?.country
                        ? `${session.location.city}, ${session.location.country}`
                        : 'Unknown'}
                    </span>
                  </td>
                  <td className="p-4">
                    <SessionStatusBadge status={session.status || 'active'} />
                  </td>
                  <td className="text-muted-foreground p-4 text-sm">
                    {formatTimeAgo(session.last_active_at || session.created_at)}
                  </td>
                  <td className="p-4">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={session.is_current || revokingId === session.id}
                        >
                          {revokingId === session.id ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <MoreHorizontal className="size-4" />
                          )}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => revokeSession(session.id)}
                        >
                          <Trash2 className="mr-2 size-4" />
                          Revoke Session
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="text-muted-foreground text-sm">
        Active: {activeSessions} | Total: {sessions.length}
      </div>
    </div>
  )
}

function DeviceIcon({ type }: { type?: string }) {
  switch (type?.toLowerCase()) {
    case 'mobile':
      return <Smartphone className="text-muted-foreground size-4" />
    case 'tablet':
      return <Tablet className="text-muted-foreground size-4" />
    case 'desktop':
      return <Monitor className="text-muted-foreground size-4" />
    default:
      return <Globe className="text-muted-foreground size-4" />
  }
}

function SessionStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-green-500/10 text-green-600 dark:text-green-400',
    expired: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
    revoked: 'bg-destructive/10 text-destructive',
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${colors[status] || colors.active}`}>
      {status}
    </span>
  )
}

function parseDeviceType(userAgent?: string): string {
  if (!userAgent) return 'unknown'
  if (/iPad/i.test(userAgent)) return 'tablet'
  if (/Mobile|Android|iPhone/i.test(userAgent)) return 'mobile'
  return 'desktop'
}

function parseBrowser(userAgent?: string): string {
  if (!userAgent) return 'Unknown'
  if (/curl/i.test(userAgent)) return 'curl (CLI)'
  if (/Edg\/(\d+)/i.test(userAgent)) return `Edge ${userAgent.match(/Edg\/(\d+)/i)?.[1] || ''}`
  if (/Chrome\/(\d+)/i.test(userAgent)) return `Chrome ${userAgent.match(/Chrome\/(\d+)/i)?.[1] || ''}`
  if (/Firefox\/(\d+)/i.test(userAgent)) return `Firefox ${userAgent.match(/Firefox\/(\d+)/i)?.[1] || ''}`
  if (/Safari/i.test(userAgent) && !/Chrome/i.test(userAgent)) return 'Safari'
  return 'Unknown'
}

function parseOS(userAgent?: string): string {
  if (!userAgent) return 'Unknown'
  if (/Windows/i.test(userAgent)) return 'Windows'
  if (/Mac OS X/i.test(userAgent)) return 'macOS'
  if (/Linux/i.test(userAgent)) return 'Linux'
  if (/Android/i.test(userAgent)) return 'Android'
  if (/iOS|iPhone|iPad/i.test(userAgent)) return 'iOS'
  return 'Unknown'
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}
