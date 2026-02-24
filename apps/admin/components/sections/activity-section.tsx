'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Loader2,
  RefreshCw,
  Clock,
  Filter,
  LogIn,
  UserPlus,
  KeyRound,
  ShieldCheck,
  LogOut,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Activity,
} from 'lucide-react'
import { adminAPI, type ActivityLog } from '@/lib/admin-api'

const AUTO_REFRESH_INTERVAL = 10_000

const ACTION_TYPES = [
  'all',
  'login',
  'login_failed',
  'register',
  'logout',
  'mfa_setup',
  'mfa_verify',
  'password_reset',
  'password_change',
  'token_refresh',
  'account_locked',
  'session_revoked',
] as const

type ActionFilter = (typeof ACTION_TYPES)[number]

const TIME_RANGES = [
  { label: 'Last hour', value: 60 },
  { label: 'Last 6 hours', value: 360 },
  { label: 'Last 24 hours', value: 1440 },
  { label: 'Last 7 days', value: 10080 },
  { label: 'All time', value: 0 },
] as const

const ACTION_ICON_MAP: Record<string, React.ElementType> = {
  login: LogIn,
  login_success: LogIn,
  login_failed: XCircle,
  register: UserPlus,
  logout: LogOut,
  mfa_setup: ShieldCheck,
  mfa_verify: ShieldCheck,
  password_reset: KeyRound,
  password_change: KeyRound,
  token_refresh: RefreshCw,
  account_locked: AlertTriangle,
  session_revoked: AlertTriangle,
}

const ACTION_COLOR_MAP: Record<string, string> = {
  login: 'text-green-600 dark:text-green-400 bg-green-500/10',
  login_success: 'text-green-600 dark:text-green-400 bg-green-500/10',
  login_failed: 'text-red-600 dark:text-red-400 bg-red-500/10',
  register: 'text-blue-600 dark:text-blue-400 bg-blue-500/10',
  logout: 'text-muted-foreground bg-muted',
  mfa_setup: 'text-purple-600 dark:text-purple-400 bg-purple-500/10',
  mfa_verify: 'text-purple-600 dark:text-purple-400 bg-purple-500/10',
  password_reset: 'text-orange-600 dark:text-orange-400 bg-orange-500/10',
  password_change: 'text-orange-600 dark:text-orange-400 bg-orange-500/10',
  token_refresh: 'text-muted-foreground bg-muted',
  account_locked: 'text-red-600 dark:text-red-400 bg-red-500/10',
  session_revoked: 'text-yellow-600 dark:text-yellow-400 bg-yellow-500/10',
}

function getActionIcon(action: string): React.ElementType {
  const normalized = action.toLowerCase().replace(/[\s-]/g, '_')
  return ACTION_ICON_MAP[normalized] ?? Activity
}

function getActionColor(action: string): string {
  const normalized = action.toLowerCase().replace(/[\s-]/g, '_')
  return ACTION_COLOR_MAP[normalized] ?? 'text-muted-foreground bg-muted'
}

function formatActionLabel(action: string): string {
  return action
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

interface ActivityStats {
  total: number
  successCount: number
  failureCount: number
  successRate: number
  byType: Record<string, number>
}

function computeStats(logs: ActivityLog[]): ActivityStats {
  const total = logs.length
  const failureActions = ['login_failed', 'account_locked']
  const successActions = ['login', 'login_success', 'register', 'mfa_verify']

  let successCount = 0
  let failureCount = 0
  const byType: Record<string, number> = {}

  for (const log of logs) {
    const normalized = log.action.toLowerCase().replace(/[\s-]/g, '_')
    byType[log.action] = (byType[log.action] || 0) + 1

    if (successActions.includes(normalized)) successCount++
    if (failureActions.includes(normalized)) failureCount++
  }

  const authTotal = successCount + failureCount
  const successRate = authTotal > 0 ? (successCount / authTotal) * 100 : 100

  return { total, successCount, failureCount, successRate, byType }
}

export function ActivitySection() {
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all')
  const [timeRange, setTimeRange] = useState<number>(1440)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchLogs = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      const data = await adminAPI.getActivityLogs(50)
      setLogs(data)
      setError(null)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch activity logs')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchLogs()
    const interval = setInterval(() => fetchLogs(), AUTO_REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchLogs])

  const filteredLogs = useMemo(() => {
    let result = logs

    // Filter by time range
    if (timeRange > 0) {
      const cutoff = Date.now() - timeRange * 60 * 1000
      result = result.filter((log) => new Date(log.created_at).getTime() >= cutoff)
    }

    // Filter by action type
    if (actionFilter !== 'all') {
      result = result.filter((log) => {
        const normalized = log.action.toLowerCase().replace(/[\s-]/g, '_')
        return normalized === actionFilter
      })
    }

    return result
  }, [logs, actionFilter, timeRange])

  const stats = useMemo(() => computeStats(filteredLogs), [filteredLogs])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && logs.length === 0) {
    return (
      <div className="space-y-6">
        <h2 className="text-foreground text-2xl font-bold">Activity Logs</h2>
        <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
          <p className="text-destructive">{error}</p>
          <button
            onClick={() => fetchLogs(true)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-3 rounded-lg px-4 py-2 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const topActionTypes = Object.entries(stats.byType)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-2xl font-bold">Activity Logs</h2>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-muted-foreground flex items-center gap-1 text-xs">
              <Clock className="size-3" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => fetchLogs(true)}
            disabled={refreshing}
            className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg p-2 transition-colors disabled:opacity-50"
            aria-label="Refresh activity logs"
          >
            <RefreshCw className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Activity className="text-muted-foreground size-4" />
            <span className="text-muted-foreground text-xs">Total Events</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">{stats.total}</p>
        </div>
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-green-500" />
            <span className="text-muted-foreground text-xs">Auth Success</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">{stats.successCount}</p>
        </div>
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <XCircle className="size-4 text-red-500" />
            <span className="text-muted-foreground text-xs">Auth Failures</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">{stats.failureCount}</p>
        </div>
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-blue-500" />
            <span className="text-muted-foreground text-xs">Success Rate</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">
            {stats.successRate.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Activity by Type breakdown */}
      {topActionTypes.length > 0 && (
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 text-sm font-semibold">Activity by Type</h3>
          <div className="space-y-2.5">
            {topActionTypes.map(([action, count]) => {
              const percentage = stats.total > 0 ? (count / stats.total) * 100 : 0
              const colorClass = getActionColor(action)
              return (
                <div key={action} className="flex items-center gap-3">
                  <span className="text-muted-foreground w-32 truncate text-xs">
                    {formatActionLabel(action)}
                  </span>
                  <div className="bg-muted flex-1 overflow-hidden rounded-full">
                    <div
                      className={`h-2 rounded-full transition-all duration-300 ${
                        colorClass.includes('green')
                          ? 'bg-green-500/60'
                          : colorClass.includes('red')
                            ? 'bg-red-500/60'
                            : colorClass.includes('blue')
                              ? 'bg-blue-500/60'
                              : colorClass.includes('purple')
                                ? 'bg-purple-500/60'
                                : colorClass.includes('orange')
                                  ? 'bg-orange-500/60'
                                  : 'bg-muted-foreground/30'
                      }`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-muted-foreground w-12 text-right font-mono text-xs">
                    {count}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Filter className="text-muted-foreground size-4" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value as ActionFilter)}
            className="bg-card border-border text-foreground rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Filter by action type"
          >
            {ACTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {type === 'all' ? 'All Actions' : formatActionLabel(type)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="text-muted-foreground size-4" />
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="bg-card border-border text-foreground rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Filter by time range"
          >
            {TIME_RANGES.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
        </div>
        <span className="text-muted-foreground text-xs">
          Showing {filteredLogs.length} of {logs.length} events
        </span>
      </div>

      {/* Activity Feed */}
      <div className="bg-card border-border rounded-lg border">
        {filteredLogs.length === 0 ? (
          <div className="p-8 text-center">
            <Activity className="text-muted-foreground mx-auto mb-3 size-8" />
            <p className="text-muted-foreground text-sm">
              No activity logs match the current filters.
            </p>
          </div>
        ) : (
          <div className="divide-border divide-y">
            {filteredLogs.map((log) => {
              const Icon = getActionIcon(log.action)
              const colorClass = getActionColor(log.action)

              return (
                <div
                  key={log.id}
                  className="hover:bg-muted/50 flex items-start gap-3 p-4 transition-colors"
                >
                  <div
                    className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full ${colorClass}`}
                  >
                    <Icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-foreground text-sm font-medium">
                          {formatActionLabel(log.action)}
                        </p>
                        <p className="text-muted-foreground truncate text-xs">
                          {log.user_email}
                        </p>
                      </div>
                      <span
                        className="text-muted-foreground shrink-0 text-xs"
                        title={new Date(log.created_at).toLocaleString()}
                      >
                        {timeAgo(log.created_at)}
                      </span>
                    </div>
                    {(log.ip_address || log.user_agent) && (
                      <div className="text-muted-foreground mt-1 flex flex-wrap gap-3 text-xs">
                        {log.ip_address && <span>IP: {log.ip_address}</span>}
                        {log.user_agent && (
                          <span className="max-w-xs truncate">{log.user_agent}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Auto-refresh indicator */}
      <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
        <RefreshCw className="size-3" />
        Auto-refreshes every 10 seconds
      </p>
    </div>
  )
}
