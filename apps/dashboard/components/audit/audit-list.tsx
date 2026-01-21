'use client'

import { useState, useEffect } from 'react'
import { Button } from '@janua/ui'
import {
  Search,
  Loader2,
  AlertCircle,
  RefreshCw,
  Download,
  Filter,
  ChevronDown,
  User,
  Globe,
  Shield,
  Clock
} from 'lucide-react'
import { apiCall } from '../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface AuditLog {
  id: string
  action: string
  user_id: string | null
  user_email: string | null
  resource_type: string | null
  resource_id: string | null
  details: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  timestamp: string
}

interface AuditStats {
  total_events: number
  events_by_action: Record<string, number>
  events_by_user: Array<{ user_id: string; email: string; count: number }>
  events_by_resource_type: Record<string, number>
  unique_users: number
  unique_ips: number
}

export function AuditList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [selectedAction, setSelectedAction] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)
  const [availableActions, setAvailableActions] = useState<string[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [cursor, setCursor] = useState<string | null>(null)

  useEffect(() => {
    fetchLogs()
    fetchStats()
    fetchAvailableActions()
  }, [])

  const fetchLogs = async (append = false) => {
    try {
      if (!append) setLoading(true)
      setError(null)

      let url = `${API_BASE_URL}/api/v1/audit-logs/?limit=50`
      if (selectedAction) url += `&action=${selectedAction}`
      if (cursor && append) url += `&cursor=${cursor}`

      const response = await apiCall(url)

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication required')
        }
        throw new Error('Failed to fetch audit logs')
      }

      const data = await response.json()

      if (append) {
        setLogs(prev => [...prev, ...(data.logs || [])])
      } else {
        setLogs(data.logs || [])
      }

      setHasMore(data.has_more || false)
      setCursor(data.cursor || null)
    } catch (err) {
      console.error('Failed to fetch audit logs:', err)
      setError(err instanceof Error ? err.message : 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/audit-logs/stats`)
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (err) {
      console.error('Failed to fetch audit stats:', err)
    }
  }

  const fetchAvailableActions = async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/audit-logs/actions/list`)
      if (response.ok) {
        const data = await response.json()
        setAvailableActions(data.actions || [])
      }
    } catch (err) {
      console.error('Failed to fetch available actions:', err)
    }
  }

  const exportLogs = async (format: 'json' | 'csv') => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/audit-logs/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format })
      })

      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `audit_logs.${format}`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      } else {
        alert('Failed to export audit logs')
      }
    } catch (err) {
      console.error('Failed to export logs:', err)
      alert('Failed to export audit logs')
    }
  }

  const formatDateTime = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
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
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  const getActionColor = (action: string): string => {
    if (action.includes('create') || action.includes('register')) {
      return 'bg-green-500/10 text-green-600 dark:text-green-400'
    }
    if (action.includes('delete') || action.includes('revoke')) {
      return 'bg-destructive/10 text-destructive'
    }
    if (action.includes('update') || action.includes('modify')) {
      return 'bg-primary/10 text-primary'
    }
    if (action.includes('login') || action.includes('signin')) {
      return 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
    }
    if (action.includes('logout') || action.includes('signout')) {
      return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
    }
    return 'bg-muted text-muted-foreground'
  }

  const filteredLogs = logs.filter(log =>
    (log.user_email?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false) ||
    log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.ip_address?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false) ||
    (log.resource_type?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
  )

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading audit logs...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Audit Logs</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={() => fetchLogs()} variant="outline">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Stats Banner */}
      {stats && (
        <div className="bg-muted/50 grid grid-cols-4 gap-4 rounded-lg p-4">
          <div>
            <div className="text-2xl font-bold">{stats.total_events}</div>
            <div className="text-muted-foreground text-sm">Total Events</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.unique_users}</div>
            <div className="text-muted-foreground text-sm">Unique Users</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.unique_ips}</div>
            <div className="text-muted-foreground text-sm">Unique IPs</div>
          </div>
          <div>
            <div className="text-2xl font-bold">
              {Object.keys(stats.events_by_action).length}
            </div>
            <div className="text-muted-foreground text-sm">Action Types</div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative max-w-md flex-1">
          <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
          <input
            placeholder="Search by user, action, IP, or resource..."
            className="focus:ring-primary w-full rounded-md border py-2 pl-8 pr-4 focus:outline-none focus:ring-2"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-2 size-4" />
            Filters
            <ChevronDown className={`ml-1 size-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchLogs()}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportLogs('json')}>
            <Download className="mr-2 size-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="bg-muted/30 space-y-3 rounded-lg p-4">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium">Action Type:</label>
            <select
              className="rounded-md border px-3 py-1.5 text-sm"
              value={selectedAction}
              onChange={(e) => {
                setSelectedAction(e.target.value)
                setCursor(null)
                fetchLogs()
              }}
            >
              <option value="">All Actions</option>
              {availableActions.map(action => (
                <option key={action} value={action}>{action}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/50 border-b">
              <th className="p-4 text-left text-sm font-medium">Timestamp</th>
              <th className="p-4 text-left text-sm font-medium">Action</th>
              <th className="p-4 text-left text-sm font-medium">User</th>
              <th className="p-4 text-left text-sm font-medium">Resource</th>
              <th className="p-4 text-left text-sm font-medium">IP Address</th>
              <th className="p-4 text-left text-sm font-medium">Details</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground p-8 text-center">
                  {searchTerm ? 'No audit logs match your search' : 'No audit logs found'}
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-muted/50 border-b">
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <Clock className="text-muted-foreground size-4" />
                      <div>
                        <div className="text-sm font-medium">{formatTimeAgo(log.timestamp)}</div>
                        <div className="text-muted-foreground text-xs">{formatDateTime(log.timestamp)}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ${getActionColor(log.action)}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <User className="text-muted-foreground size-4" />
                      <div>
                        <div className="text-sm">{log.user_email || 'System'}</div>
                        {log.user_id && (
                          <div className="text-muted-foreground font-mono text-xs">
                            {log.user_id.slice(0, 8)}...
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    {log.resource_type ? (
                      <div>
                        <div className="text-sm font-medium">{log.resource_type}</div>
                        {log.resource_id && (
                          <div className="text-muted-foreground font-mono text-xs">
                            {log.resource_id.slice(0, 8)}...
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <Globe className="text-muted-foreground size-4" />
                      <span className="font-mono text-sm">{log.ip_address || '-'}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    {log.details ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => alert(JSON.stringify(log.details, null, 2))}
                        title="View details"
                      >
                        <Shield className="size-4" />
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Load More */}
      <div className="text-muted-foreground flex items-center justify-between text-sm">
        <div>
          Showing {filteredLogs.length} audit log entries
        </div>
        {hasMore && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchLogs(true)}
            disabled={loading}
          >
            {loading ? (
              <><Loader2 className="mr-2 size-4 animate-spin" /> Loading...</>
            ) : (
              'Load More'
            )}
          </Button>
        )}
      </div>

      {/* Top Actions */}
      {stats && Object.keys(stats.events_by_action).length > 0 && (
        <div className="bg-muted/30 rounded-lg p-4">
          <h4 className="mb-3 text-sm font-medium">Top Actions (Last 30 Days)</h4>
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(stats.events_by_action)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([action, count]) => (
                <div key={action} className="bg-background flex items-center justify-between rounded border p-2">
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${getActionColor(action)}`}>
                    {action}
                  </span>
                  <span className="text-sm font-medium">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
