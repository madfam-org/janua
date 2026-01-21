'use client'

import { useState, useEffect } from 'react'
import { Button } from '@janua/ui'
import { MoreHorizontal, Search, Shield, Globe, Smartphone, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { apiCall } from '../../lib/auth'

// API base URL for production - use public API URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface Session {
  id: string
  userId: string
  userEmail: string
  device: string
  browser: string
  ip: string
  location: string
  startedAt: string
  lastActivity: string
  status: 'active' | 'expired' | 'revoked'
}

interface ActivityLog {
  id: string
  user_id: string
  user_email: string
  action: string
  details: {
    method?: string
  }
  ip_address: string
  user_agent: string
  created_at: string
}

interface StatsResponse {
  total_sessions: number
  active_sessions: number
}

export function SessionList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<StatsResponse | null>(null)

  useEffect(() => {
    fetchSessions()
  }, [])

  const fetchSessions = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch stats to get session counts
      const [activityResponse, statsResponse] = await Promise.all([
        apiCall(`${API_BASE_URL}/api/v1/admin/activity-logs?per_page=50`),
        apiCall(`${API_BASE_URL}/api/v1/admin/stats`)
      ])

      if (!activityResponse.ok) {
        throw new Error('Failed to fetch activity logs')
      }

      if (statsResponse.ok) {
        const statsData = await statsResponse.json()
        setStats(statsData)
      }

      const activityLogs: ActivityLog[] = await activityResponse.json()

      // Convert activity logs to session data
      // Each signin action represents a session
      const sessionList: Session[] = activityLogs
        .filter(log => log.action === 'signin')
        .map(log => {
          const browserInfo = parseUserAgent(log.user_agent)
          return {
            id: log.id,
            userId: log.user_id,
            userEmail: log.user_email,
            device: browserInfo.device,
            browser: browserInfo.browser,
            ip: log.ip_address,
            location: 'Unknown', // Would need IP geolocation service
            startedAt: formatDateTime(log.created_at),
            lastActivity: formatTimeAgo(log.created_at),
            status: isSessionActive(log.created_at) ? 'active' : 'expired'
          }
        })

      setSessions(sessionList)
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
      setError(err instanceof Error ? err.message : 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }

  const parseUserAgent = (userAgent: string): { device: string; browser: string } => {
    if (!userAgent) return { device: 'Unknown', browser: 'Unknown' }

    let device = 'Desktop'
    let browser = 'Unknown'

    // Detect device
    if (/Mobile|Android|iPhone|iPad/i.test(userAgent)) {
      if (/iPad/i.test(userAgent)) {
        device = 'Tablet'
      } else {
        device = 'Mobile'
      }
    }

    // Detect browser
    if (/curl/i.test(userAgent)) {
      browser = 'curl (CLI)'
    } else if (/Chrome\/(\d+)/i.test(userAgent)) {
      const match = userAgent.match(/Chrome\/(\d+)/i)
      browser = `Chrome ${match?.[1] || ''}`
    } else if (/Firefox\/(\d+)/i.test(userAgent)) {
      const match = userAgent.match(/Firefox\/(\d+)/i)
      browser = `Firefox ${match?.[1] || ''}`
    } else if (/Safari\/(\d+)/i.test(userAgent) && !/Chrome/i.test(userAgent)) {
      browser = 'Safari'
    } else if (/Edge\/(\d+)/i.test(userAgent)) {
      const match = userAgent.match(/Edge\/(\d+)/i)
      browser = `Edge ${match?.[1] || ''}`
    }

    return { device, browser }
  }

  const formatDateTime = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatTimeAgo = (dateString: string): string => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    return date.toLocaleDateString()
  }

  const isSessionActive = (dateString: string): boolean => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = diffMs / 3600000
    // Consider sessions active if within 24 hours
    return diffHours < 24
  }

  const getStatusColor = (status: Session['status']) => {
    switch (status) {
      case 'active':
        return 'bg-green-500/10 text-green-600 dark:text-green-400'
      case 'expired':
        return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
      case 'revoked':
        return 'bg-destructive/10 text-destructive'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getDeviceIcon = (device: string) => {
    switch (device.toLowerCase()) {
      case 'mobile':
        return <Smartphone className="size-4" />
      case 'desktop':
        return <Globe className="size-4" />
      default:
        return <Shield className="size-4" />
    }
  }

  const filteredSessions = sessions.filter(session =>
    session.userEmail.toLowerCase().includes(searchTerm.toLowerCase()) ||
    session.ip.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const activeSessions = sessions.filter(s => s.status === 'active').length

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
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Stats Banner */}
      {stats && (
        <div className="bg-muted/50 grid grid-cols-2 gap-4 rounded-lg p-4">
          <div>
            <div className="text-2xl font-bold">{stats.active_sessions}</div>
            <div className="text-muted-foreground text-sm">Active Sessions</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.total_sessions}</div>
            <div className="text-muted-foreground text-sm">Total Sessions</div>
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
          <input
            placeholder="Search sessions by email or IP..."
            className="focus:ring-primary w-full rounded-md border py-2 pl-8 pr-4 focus:outline-none focus:ring-2"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={fetchSessions}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button variant="destructive" size="sm" disabled>
            Revoke All Expired
          </Button>
        </div>
      </div>

      {/* Session Table */}
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/50 border-b">
              <th className="p-4 text-left text-sm font-medium">User</th>
              <th className="p-4 text-left text-sm font-medium">Device & Browser</th>
              <th className="p-4 text-left text-sm font-medium">IP Address</th>
              <th className="p-4 text-left text-sm font-medium">Status</th>
              <th className="p-4 text-left text-sm font-medium">Last Activity</th>
              <th className="p-4 text-left text-sm font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {filteredSessions.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground p-8 text-center">
                  {searchTerm ? 'No sessions match your search' : 'No sessions found'}
                </td>
              </tr>
            ) : (
              filteredSessions.map((session) => (
                <tr key={session.id} className="hover:bg-muted/50 border-b">
                  <td className="p-4">
                    <div>
                      <div className="font-medium">{session.userEmail}</div>
                      <div className="text-muted-foreground font-mono text-xs">{session.userId.slice(0, 8)}...</div>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      {getDeviceIcon(session.device)}
                      <div>
                        <div className="text-sm font-medium">{session.device}</div>
                        <div className="text-muted-foreground text-xs">{session.browser}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="font-mono text-sm">{session.ip}</div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${getStatusColor(session.status)}`}>
                      {session.status}
                    </span>
                  </td>
                  <td className="text-muted-foreground p-4 text-sm">
                    {session.lastActivity}
                  </td>
                  <td className="p-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={session.status !== 'active'}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="text-muted-foreground flex items-center justify-between text-sm">
        <div>
          Active: {activeSessions} | Total: {sessions.length}
        </div>
        <div className="flex space-x-2">
          <Button variant="outline" size="sm" disabled>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={sessions.length < 50}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
