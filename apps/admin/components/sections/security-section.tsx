'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Loader2,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  AlertTriangle,
  Lock,
  Fingerprint,
  Ban,
  TrendingUp,
  TrendingDown,
  XCircle,
  Activity,
} from 'lucide-react'
import { adminAPI, type AdminStats, type ActivityLog } from '@/lib/admin-api'

interface SecurityMetrics {
  failedLogins24h: number
  failedLoginsTotal: number
  failedLoginTrend: 'up' | 'down' | 'stable'
  accountLockouts: number
  suspiciousIps: { ip: string; count: number; lastSeen: string }[]
  mfaAdoptionRate: number
  mfaEnabledUsers: number
  totalUsers: number
  recentSecurityEvents: SecurityEvent[]
}

interface SecurityEvent {
  id: string
  type: 'failed_login' | 'account_locked' | 'session_revoked' | 'mfa_failed' | 'suspicious_ip'
  description: string
  email: string
  ip: string | null
  timestamp: string
  severity: 'low' | 'medium' | 'high' | 'critical'
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
  high: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
  medium: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
  low: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
}

const SEVERITY_ICONS: Record<string, React.ElementType> = {
  critical: ShieldOff,
  high: ShieldAlert,
  medium: AlertTriangle,
  low: Shield,
}

function deriveSecurityMetrics(
  stats: AdminStats | null,
  logs: ActivityLog[]
): SecurityMetrics {
  const now = Date.now()
  const h24 = 24 * 60 * 60 * 1000
  const h12 = 12 * 60 * 60 * 1000

  // Filter failed logins
  const failedLogins = logs.filter((log) => {
    const action = log.action.toLowerCase().replace(/[\s-]/g, '_')
    return action === 'login_failed'
  })

  const failedLogins24h = failedLogins.filter(
    (log) => now - new Date(log.created_at).getTime() < h24
  ).length

  // Trend: compare first 12h vs last 12h
  const recentFailed = failedLogins.filter(
    (log) => now - new Date(log.created_at).getTime() < h12
  ).length
  const olderFailed = failedLogins.filter((log) => {
    const age = now - new Date(log.created_at).getTime()
    return age >= h12 && age < h24
  }).length

  let failedLoginTrend: 'up' | 'down' | 'stable' = 'stable'
  if (recentFailed > olderFailed * 1.2) failedLoginTrend = 'up'
  else if (recentFailed < olderFailed * 0.8) failedLoginTrend = 'down'

  // Account lockouts
  const accountLockouts = logs.filter((log) => {
    const action = log.action.toLowerCase().replace(/[\s-]/g, '_')
    return action === 'account_locked'
  }).length

  // Suspicious IPs (IPs with 3+ failed logins)
  const ipCounts: Record<string, { count: number; lastSeen: string }> = {}
  for (const log of failedLogins) {
    if (log.ip_address) {
      if (!ipCounts[log.ip_address]) {
        ipCounts[log.ip_address] = { count: 0, lastSeen: log.created_at }
      }
      ipCounts[log.ip_address].count++
      if (new Date(log.created_at) > new Date(ipCounts[log.ip_address].lastSeen)) {
        ipCounts[log.ip_address].lastSeen = log.created_at
      }
    }
  }

  const suspiciousIps = Object.entries(ipCounts)
    .filter(([, data]) => data.count >= 3)
    .map(([ip, data]) => ({ ip, count: data.count, lastSeen: data.lastSeen }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  // MFA adoption
  const mfaEnabledUsers = stats?.mfa_enabled_users ?? 0
  const totalUsers = stats?.total_users ?? 1
  const mfaAdoptionRate = totalUsers > 0 ? (mfaEnabledUsers / totalUsers) * 100 : 0

  // Recent security events from logs
  const securityActions = ['login_failed', 'account_locked', 'session_revoked']
  const recentSecurityEvents: SecurityEvent[] = logs
    .filter((log) => {
      const action = log.action.toLowerCase().replace(/[\s-]/g, '_')
      return securityActions.includes(action)
    })
    .slice(0, 20)
    .map((log) => {
      const action = log.action.toLowerCase().replace(/[\s-]/g, '_')
      let severity: SecurityEvent['severity'] = 'low'
      let type: SecurityEvent['type'] = 'failed_login'

      if (action === 'account_locked') {
        severity = 'high'
        type = 'account_locked'
      } else if (action === 'session_revoked') {
        severity = 'medium'
        type = 'session_revoked'
      } else if (action === 'login_failed') {
        const ipData = log.ip_address ? ipCounts[log.ip_address] : null
        severity = ipData && ipData.count >= 5 ? 'critical' : ipData && ipData.count >= 3 ? 'high' : 'medium'
        type = 'failed_login'
      }

      return {
        id: log.id,
        type,
        description: log.action.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
        email: log.user_email,
        ip: log.ip_address,
        timestamp: log.created_at,
        severity,
      }
    })

  return {
    failedLogins24h,
    failedLoginsTotal: failedLogins.length,
    failedLoginTrend,
    accountLockouts,
    suspiciousIps,
    mfaAdoptionRate,
    mfaEnabledUsers,
    totalUsers,
    recentSecurityEvents,
  }
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

export function SecuritySection() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revoking, setRevoking] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      const [statsData, logsData] = await Promise.all([
        adminAPI.getStats(),
        adminAPI.getActivityLogs(50),
      ])
      setStats(statsData)
      setLogs(logsData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch security data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const metrics = useMemo(() => deriveSecurityMetrics(stats, logs), [stats, logs])

  const handleRevokeAllSessions = async () => {
    if (
      !confirm(
        'Are you sure you want to revoke ALL user sessions? This will log out every user immediately.'
      )
    ) {
      return
    }
    setRevoking(true)
    try {
      await adminAPI.revokeAllSessions()
      alert('All sessions revoked successfully')
      fetchData(true)
    } catch {
      alert('Failed to revoke sessions')
    } finally {
      setRevoking(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && !stats) {
    return (
      <div className="space-y-6">
        <h2 className="text-foreground text-2xl font-bold">Security and Compliance</h2>
        <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
          <p className="text-destructive">{error}</p>
          <button
            onClick={() => fetchData(true)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-3 rounded-lg px-4 py-2 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const mfaBarColor =
    metrics.mfaAdoptionRate >= 80
      ? 'bg-green-500 dark:bg-green-400'
      : metrics.mfaAdoptionRate >= 50
        ? 'bg-yellow-500 dark:bg-yellow-400'
        : 'bg-red-500 dark:bg-red-400'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-2xl font-bold">Security and Compliance</h2>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg p-2 transition-colors disabled:opacity-50"
          aria-label="Refresh security data"
        >
          <RefreshCw className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {/* Failed Logins */}
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <XCircle className="size-4 text-red-500" />
              <span className="text-muted-foreground text-xs">Failed Logins (24h)</span>
            </div>
            {metrics.failedLoginTrend === 'up' && (
              <TrendingUp className="size-4 text-red-500" />
            )}
            {metrics.failedLoginTrend === 'down' && (
              <TrendingDown className="size-4 text-green-500" />
            )}
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">
            {metrics.failedLogins24h}
          </p>
          <p className="text-muted-foreground text-xs">
            {metrics.failedLoginsTotal} total in logs
          </p>
        </div>

        {/* Account Lockouts */}
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Lock className="size-4 text-orange-500" />
            <span className="text-muted-foreground text-xs">Account Lockouts</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">
            {metrics.accountLockouts}
          </p>
        </div>

        {/* Suspicious IPs */}
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Ban className="size-4 text-yellow-500" />
            <span className="text-muted-foreground text-xs">Suspicious IPs</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">
            {metrics.suspiciousIps.length}
          </p>
          <p className="text-muted-foreground text-xs">3+ failed attempts</p>
        </div>

        {/* MFA Adoption */}
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Fingerprint className="size-4 text-purple-500" />
            <span className="text-muted-foreground text-xs">MFA Adoption</span>
          </div>
          <p className="text-foreground mt-1 text-2xl font-semibold">
            {metrics.mfaAdoptionRate.toFixed(1)}%
          </p>
          <p className="text-muted-foreground text-xs">
            {metrics.mfaEnabledUsers} of {metrics.totalUsers} users
          </p>
        </div>
      </div>

      {/* MFA Adoption Progress */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-3 flex items-center gap-2 text-lg font-semibold">
          <Fingerprint className="size-5" />
          MFA Adoption Rate
        </h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {metrics.mfaEnabledUsers} users with MFA enabled
            </span>
            <span className="text-foreground font-medium">
              {metrics.mfaAdoptionRate.toFixed(1)}%
            </span>
          </div>
          <div className="bg-muted h-3 overflow-hidden rounded-full">
            <div
              className={`h-full rounded-full transition-all duration-500 ${mfaBarColor}`}
              style={{ width: `${metrics.mfaAdoptionRate}%` }}
            />
          </div>
          <p className="text-muted-foreground text-xs">
            {metrics.mfaAdoptionRate >= 80
              ? 'Healthy MFA adoption across the platform.'
              : metrics.mfaAdoptionRate >= 50
                ? 'MFA adoption could be improved. Consider enforcing MFA for sensitive roles.'
                : 'Low MFA adoption. Strongly consider enforcing MFA policies.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Suspicious IPs Table */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <Ban className="size-5" />
            Suspicious IPs
          </h3>
          {metrics.suspiciousIps.length === 0 ? (
            <div className="py-6 text-center">
              <ShieldCheck className="mx-auto mb-2 size-8 text-green-500" />
              <p className="text-muted-foreground text-sm">
                No suspicious IP addresses detected.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {metrics.suspiciousIps.map((entry) => (
                <div
                  key={entry.ip}
                  className="bg-muted/50 flex items-center justify-between rounded-lg p-3"
                >
                  <div>
                    <span className="text-foreground font-mono text-sm">{entry.ip}</span>
                    <p className="text-muted-foreground text-xs">
                      Last seen: {timeAgo(entry.lastSeen)}
                    </p>
                  </div>
                  <span className="rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-medium text-red-600 dark:text-red-400">
                    {entry.count} failures
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Attack Protection Status */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <Shield className="size-5" />
            Attack Protection
          </h3>
          <div className="space-y-3">
            {[
              {
                name: 'Rate Limiting',
                enabled: true,
                description: 'API rate limiting active on all endpoints',
              },
              {
                name: 'Brute Force Protection',
                enabled: true,
                description: 'Account lockout after repeated failed attempts',
              },
              {
                name: 'CSRF Protection',
                enabled: true,
                description: 'Cross-site request forgery tokens validated',
              },
              {
                name: 'Bot Detection',
                enabled: false,
                description: 'Automated bot detection and challenge',
              },
              {
                name: 'IP Blocklist',
                enabled: metrics.suspiciousIps.length > 0,
                description: `${metrics.suspiciousIps.length} IP(s) flagged for review`,
              },
            ].map((feature) => (
              <div
                key={feature.name}
                className="bg-muted/50 flex items-center justify-between rounded-lg p-3"
              >
                <div>
                  <span className="text-foreground text-sm font-medium">{feature.name}</span>
                  <p className="text-muted-foreground text-xs">{feature.description}</p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    feature.enabled
                      ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {feature.enabled ? 'Active' : 'Inactive'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Security Events */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
          <Activity className="size-5" />
          Recent Security Events
        </h3>
        {metrics.recentSecurityEvents.length === 0 ? (
          <div className="py-6 text-center">
            <ShieldCheck className="mx-auto mb-2 size-8 text-green-500" />
            <p className="text-muted-foreground text-sm">No recent security events.</p>
          </div>
        ) : (
          <div className="divide-border divide-y">
            {metrics.recentSecurityEvents.map((event) => {
              const SeverityIcon = SEVERITY_ICONS[event.severity] ?? Shield
              const severityStyle = SEVERITY_STYLES[event.severity] ?? SEVERITY_STYLES.low

              return (
                <div key={event.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <div
                    className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full ${severityStyle}`}
                  >
                    <SeverityIcon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-foreground text-sm font-medium">
                          {event.description}
                        </p>
                        <p className="text-muted-foreground truncate text-xs">
                          {event.email}
                          {event.ip && ` - ${event.ip}`}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${severityStyle}`}
                        >
                          {event.severity}
                        </span>
                        <span
                          className="text-muted-foreground text-xs"
                          title={new Date(event.timestamp).toLocaleString()}
                        >
                          {timeAgo(event.timestamp)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Emergency Actions */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 text-lg font-semibold">Emergency Actions</h3>
        <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-4">
          <h4 className="text-destructive font-medium">Revoke All Sessions</h4>
          <p className="text-destructive/80 mt-1 text-sm">
            This will immediately log out all users from the platform. Use only in case of a
            confirmed security breach.
          </p>
          <button
            onClick={handleRevokeAllSessions}
            disabled={revoking}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-3 rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          >
            {revoking ? 'Revoking...' : 'Revoke All Sessions'}
          </button>
        </div>
      </div>
    </div>
  )
}
