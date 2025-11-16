import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export type AuditEventType =
  | 'auth.login'
  | 'auth.logout'
  | 'auth.failed_login'
  | 'auth.password_change'
  | 'auth.password_reset'
  | 'auth.email_change'
  | 'auth.mfa_enabled'
  | 'auth.mfa_disabled'
  | 'auth.mfa_verified'
  | 'security.session_revoked'
  | 'security.device_trusted'
  | 'security.device_revoked'
  | 'security.suspicious_activity'
  | 'admin.user_created'
  | 'admin.user_deleted'
  | 'admin.role_changed'
  | 'admin.permissions_changed'
  | 'compliance.data_export'
  | 'compliance.data_deletion'
  | 'compliance.consent_granted'
  | 'compliance.consent_revoked'

export type AuditEventCategory = 'auth' | 'security' | 'admin' | 'compliance'

export interface AuditEvent {
  /** Unique event identifier */
  id: string
  /** Event type */
  type: AuditEventType
  /** Event category */
  category: AuditEventCategory
  /** User who performed the action */
  actor: {
    id: string
    email: string
    name?: string
  }
  /** Target user/resource (if different from actor) */
  target?: {
    id: string
    email?: string
    name?: string
    type?: string
  }
  /** Event metadata */
  metadata?: Record<string, any>
  /** IP address */
  ipAddress?: string
  /** User agent */
  userAgent?: string
  /** Location */
  location?: {
    city?: string
    country?: string
  }
  /** Timestamp */
  timestamp: Date
  /** Event severity */
  severity?: 'info' | 'warning' | 'critical'
}

export interface AuditLogProps {
  /** Optional custom class name */
  className?: string
  /** List of audit events */
  events: AuditEvent[]
  /** Callback to load more events */
  onLoadMore?: () => Promise<void>
  /** Whether there are more events to load */
  hasMore?: boolean
  /** Callback to export events */
  onExport?: (format: 'csv' | 'json', filters?: AuditLogFilters) => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Custom logo URL */
  logoUrl?: string
  /** Show export functionality */
  showExport?: boolean
  /** Show filters */
  showFilters?: boolean
}

export interface AuditLogFilters {
  search?: string
  category?: AuditEventCategory | 'all'
  severity?: 'info' | 'warning' | 'critical' | 'all'
  startDate?: Date
  endDate?: Date
}

export function AuditLog({
  className,
  events,
  onLoadMore,
  hasMore = false,
  onExport,
  onError,
  logoUrl,
  showExport = true,
  showFilters = true,
}: AuditLogProps) {
  const [filters, setFilters] = React.useState<AuditLogFilters>({
    search: '',
    category: 'all',
    severity: 'all',
  })
  const [isLoadingMore, setIsLoadingMore] = React.useState(false)
  const [isExporting, setIsExporting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleLoadMore = async () => {
    if (!onLoadMore || isLoadingMore) return

    setIsLoadingMore(true)
    setError(null)

    try {
      await onLoadMore()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load more events')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoadingMore(false)
    }
  }

  const handleExport = async (format: 'csv' | 'json') => {
    if (!onExport) return

    setIsExporting(true)
    setError(null)

    try {
      await onExport(format, filters)
    } catch (err) {
      const error = err instanceof Error ? err : new Error(`Failed to export as ${format.toUpperCase()}`)
      setError(error.message)
      onError?.(error)
    } finally {
      setIsExporting(false)
    }
  }

  const getEventIcon = (category: AuditEventCategory) => {
    switch (category) {
      case 'auth':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
            />
          </svg>
        )
      case 'security':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        )
      case 'admin':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        )
      case 'compliance':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        )
    }
  }

  const getSeverityColor = (severity?: AuditEvent['severity']) => {
    switch (severity) {
      case 'critical':
        return 'text-red-600 bg-red-50'
      case 'warning':
        return 'text-yellow-600 bg-yellow-50'
      default:
        return 'text-blue-600 bg-blue-50'
    }
  }

  const formatEventType = (type: string) => {
    return type.split('.')[1].split('_').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ')
  }

  const formatTimestamp = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    if (minutes < 1) return `Just now`
    if (minutes < 60) return `${minutes}m ago • ${timeStr}`
    if (hours < 24) return `${hours}h ago • ${timeStr}`
    if (days < 7) return `${days}d ago • ${date.toLocaleDateString()}`
    return date.toLocaleString()
  }

  // Apply filters
  const filteredEvents = events.filter((event) => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      const matchesSearch =
        event.actor.email.toLowerCase().includes(searchLower) ||
        event.actor.name?.toLowerCase().includes(searchLower) ||
        event.type.toLowerCase().includes(searchLower) ||
        event.target?.email?.toLowerCase().includes(searchLower)
      if (!matchesSearch) return false
    }

    if (filters.category && filters.category !== 'all' && event.category !== filters.category) {
      return false
    }

    if (filters.severity && filters.severity !== 'all' && event.severity !== filters.severity) {
      return false
    }

    return true
  })

  return (
    <Card className={cn('w-full max-w-6xl mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-8" />
        </div>
      )}

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Audit Log</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Security events and user activity history
          </p>
        </div>

        {/* Export Actions */}
        {showExport && onExport && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExport('csv')}
              disabled={isExporting}
            >
              {isExporting ? 'Exporting...' : 'Export CSV'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExport('json')}
              disabled={isExporting}
            >
              {isExporting ? 'Exporting...' : 'Export JSON'}
            </Button>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Filters */}
      {showFilters && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label htmlFor="search">Search</Label>
            <Input
              id="search"
              type="text"
              placeholder="Search events..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category</Label>
            <select
              id="category"
              value={filters.category}
              onChange={(e) => setFilters({ ...filters, category: e.target.value as any })}
              className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
            >
              <option value="all">All Categories</option>
              <option value="auth">Authentication</option>
              <option value="security">Security</option>
              <option value="admin">Administration</option>
              <option value="compliance">Compliance</option>
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="severity">Severity</Label>
            <select
              id="severity"
              value={filters.severity}
              onChange={(e) => setFilters({ ...filters, severity: e.target.value as any })}
              className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
            >
              <option value="all">All Levels</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>
      )}

      {/* Event List */}
      <div className="space-y-3">
        {filteredEvents.length > 0 ? (
          filteredEvents.map((event) => (
            <div
              key={event.id}
              className={cn(
                'border rounded-lg p-4 hover:bg-muted/50 transition-colors',
                event.severity === 'critical' && 'border-red-200',
                event.severity === 'warning' && 'border-yellow-200'
              )}
            >
              <div className="flex items-start gap-4">
                {/* Category Icon */}
                <div className={cn('mt-0.5 p-2 rounded-lg', getSeverityColor(event.severity))}>
                  {getEventIcon(event.category)}
                </div>

                {/* Event Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex-1">
                      <h4 className="font-semibold text-sm mb-1">
                        {formatEventType(event.type)}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        <span className="font-medium">{event.actor.name || event.actor.email}</span>
                        {event.target && (
                          <>
                            {' → '}
                            <span className="font-medium">{event.target.name || event.target.email}</span>
                          </>
                        )}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimestamp(event.timestamp)}
                      </p>
                      {event.severity && (
                        <span
                          className={cn(
                            'inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium',
                            event.severity === 'critical' && 'bg-red-100 text-red-800',
                            event.severity === 'warning' && 'bg-yellow-100 text-yellow-800',
                            event.severity === 'info' && 'bg-blue-100 text-blue-800'
                          )}
                        >
                          {event.severity}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Additional Info */}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {event.ipAddress && <span>IP: {event.ipAddress}</span>}
                    {event.location && (
                      <span>
                        {event.location.city && event.location.country
                          ? `${event.location.city}, ${event.location.country}`
                          : event.location.country}
                      </span>
                    )}
                    <span className="capitalize">{event.category}</span>
                  </div>

                  {/* Metadata */}
                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-primary cursor-pointer hover:underline">
                        View metadata
                      </summary>
                      <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-auto">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            <p>No audit events found</p>
            {filters.search || filters.category !== 'all' || filters.severity !== 'all' ? (
              <p className="text-sm mt-2">Try adjusting your filters</p>
            ) : null}
          </div>
        )}
      </div>

      {/* Load More */}
      {hasMore && onLoadMore && (
        <div className="mt-6 text-center">
          <Button
            variant="outline"
            onClick={handleLoadMore}
            disabled={isLoadingMore}
          >
            {isLoadingMore ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2"></div>
                Loading...
              </>
            ) : (
              `Load more events (${filteredEvents.length} shown)`
            )}
          </Button>
        </div>
      )}

      {/* Compliance Info */}
      <div className="mt-6 bg-muted rounded-lg p-4">
        <h4 className="text-sm font-medium mb-2">Compliance & Audit Trail</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• All security events are logged for compliance purposes</li>
          <li>• Logs are retained according to your data retention policy</li>
          <li>• Export logs for GDPR, SOC 2, or HIPAA compliance audits</li>
          <li>• Event data includes IP addresses and timestamps for forensics</li>
        </ul>
      </div>
    </Card>
  )
}
