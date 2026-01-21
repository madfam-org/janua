'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import Link from 'next/link'
import {
  Lock,
  ArrowLeft,
  Search,
  RefreshCw,
  Loader2,
  AlertCircle,
  User,
  Shield,
  Key,
  Settings,
  LogIn,
  LogOut,
  UserPlus,
  UserMinus,
  FileEdit,
  Download,
} from 'lucide-react'
import { apiCall } from '../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface AuditLogEntry {
  id: string
  timestamp: string
  event_type: string
  actor_id?: string
  actor_email?: string
  actor_ip?: string
  target_type?: string
  target_id?: string
  action: string
  details?: Record<string, any>
  success: boolean
  organization_id?: string
}

const eventIcons: Record<string, any> = {
  login: LogIn,
  logout: LogOut,
  register: UserPlus,
  delete_user: UserMinus,
  update_user: FileEdit,
  mfa_enabled: Shield,
  mfa_disabled: Shield,
  password_change: Key,
  password_reset: Key,
  settings_change: Settings,
  default: Lock,
}

const eventLabels: Record<string, string> = {
  login: 'User Login',
  logout: 'User Logout',
  login_failed: 'Login Failed',
  register: 'User Registration',
  delete_user: 'User Deleted',
  update_user: 'User Updated',
  mfa_enabled: 'MFA Enabled',
  mfa_disabled: 'MFA Disabled',
  password_change: 'Password Changed',
  password_reset: 'Password Reset',
  settings_change: 'Settings Changed',
  token_refresh: 'Token Refreshed',
  session_created: 'Session Created',
  session_revoked: 'Session Revoked',
  api_key_created: 'API Key Created',
  api_key_revoked: 'API Key Revoked',
  invitation_sent: 'Invitation Sent',
  invitation_accepted: 'Invitation Accepted',
  sso_login: 'SSO Login',
  sso_config_updated: 'SSO Config Updated',
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [eventFilter, setEventFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    fetchLogs()
  }, [page, eventFilter])

  const fetchLogs = async () => {
    try {
      setLoading(true)
      setError(null)

      const params = new URLSearchParams({
        page: page.toString(),
        limit: '50',
      })

      if (eventFilter !== 'all') {
        params.append('event_type', eventFilter)
      }

      const response = await apiCall(`${API_BASE_URL}/api/v1/audit-logs?${params}`)

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('You do not have permission to view audit logs')
        }
        throw new Error('Failed to fetch audit logs')
      }

      const data = await response.json()
      const logsList = Array.isArray(data) ? data : data.logs || data.items || []

      if (page === 1) {
        setLogs(logsList)
      } else {
        setLogs((prev) => [...prev, ...logsList])
      }

      setHasMore(logsList.length === 50)
    } catch (err) {
      console.error('Failed to fetch audit logs:', err)
      setError(err instanceof Error ? err.message : 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const getEventIcon = (eventType: string) => {
    const IconComponent = eventIcons[eventType] || eventIcons.default
    return <IconComponent className="size-4" />
  }

  const getEventLabel = (eventType: string) => {
    return eventLabels[eventType] || eventType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const filteredLogs = logs.filter((log) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      log.actor_email?.toLowerCase().includes(query) ||
      log.event_type.toLowerCase().includes(query) ||
      log.action?.toLowerCase().includes(query) ||
      log.actor_ip?.includes(query)
    )
  })

  const handleExport = async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/audit-logs/export`)
      if (!response.ok) throw new Error('Failed to export logs')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to export logs')
    }
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/settings" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="size-5" />
              </Link>
              <Lock className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Audit Logs</h1>
                <p className="text-muted-foreground text-sm">
                  View security events and user activity
                </p>
              </div>
            </div>
            <Badge variant="outline">Admin Only</Badge>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Filters */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Security Events</CardTitle>
                <CardDescription>
                  {filteredLogs.length} events found
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Download className="mr-2 size-4" />
                  Export
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPage(1)
                    fetchLogs()
                  }}
                >
                  <RefreshCw className="size-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-6 flex flex-col gap-4 md:flex-row">
              <div className="relative flex-1">
                <Search className="text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2" />
                <Input
                  placeholder="Search by email, event type, or IP address..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex gap-2">
                <select
                  className="bg-background h-10 rounded-md border px-3 text-sm"
                  value={eventFilter}
                  onChange={(e) => {
                    setEventFilter(e.target.value)
                    setPage(1)
                  }}
                >
                  <option value="all">All Events</option>
                  <option value="login">Logins</option>
                  <option value="login_failed">Failed Logins</option>
                  <option value="logout">Logouts</option>
                  <option value="register">Registrations</option>
                  <option value="password_change">Password Changes</option>
                  <option value="mfa_enabled">MFA Events</option>
                  <option value="settings_change">Settings Changes</option>
                </select>
              </div>
            </div>

            {loading && page === 1 ? (
              <div className="py-8 text-center">
                <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
                <p className="text-muted-foreground mt-2 text-sm">Loading audit logs...</p>
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="text-muted-foreground py-8 text-center">
                <Lock className="mx-auto mb-4 size-12 opacity-50" />
                <p>No audit logs found</p>
                {searchQuery && (
                  <p className="mt-2 text-sm">Try adjusting your search criteria</p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {filteredLogs.map((log) => (
                  <div
                    key={log.id}
                    className={`flex items-start justify-between rounded-lg border p-4 ${
                      !log.success ? 'border-destructive/30 bg-destructive/5' : ''
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <div className={`bg-muted rounded-full p-2 ${!log.success ? 'bg-destructive/10' : ''}`}>
                        {getEventIcon(log.event_type)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{getEventLabel(log.event_type)}</span>
                          <Badge variant={log.success ? 'default' : 'destructive'}>
                            {log.success ? 'Success' : 'Failed'}
                          </Badge>
                        </div>
                        <div className="text-muted-foreground mt-1 text-sm">
                          {log.actor_email && (
                            <span className="flex items-center gap-1">
                              <User className="size-3" />
                              {log.actor_email}
                            </span>
                          )}
                          {log.actor_ip && (
                            <span className="ml-4">IP: {log.actor_ip}</span>
                          )}
                        </div>
                        {log.action && log.action !== log.event_type && (
                          <p className="mt-1 text-sm">{log.action}</p>
                        )}
                        {log.details && Object.keys(log.details).length > 0 && (
                          <details className="mt-2">
                            <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
                              Show details
                            </summary>
                            <pre className="bg-muted mt-2 max-h-32 overflow-auto rounded p-2 text-xs">
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                    <div className="text-muted-foreground whitespace-nowrap text-sm">
                      {formatDate(log.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {hasMore && !loading && (
              <div className="mt-6 text-center">
                <Button
                  variant="outline"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    'Load More'
                  )}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">About Audit Logs</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground space-y-2 text-sm">
            <p>
              Audit logs record all security-relevant events in your organization, including user
              authentication, settings changes, and administrative actions.
            </p>
            <p>
              Logs are retained for 90 days by default. Contact support if you need extended
              retention or compliance exports.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
