import * as React from 'react'
import { Button } from '../button'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export interface Session {
  /** Unique session identifier */
  id: string
  /** Device information */
  device: {
    type: 'desktop' | 'mobile' | 'tablet' | 'unknown'
    name: string
    os?: string
    browser?: string
  }
  /** Location information */
  location?: {
    city?: string
    country?: string
    ip: string
  }
  /** Session timestamps */
  createdAt: Date
  lastActiveAt: Date
  expiresAt?: Date
  /** Whether this is the current session */
  isCurrent?: boolean
  /** Security warnings */
  warnings?: Array<'unusual_location' | 'new_device' | 'suspicious_activity'>
}

export interface SessionManagementProps {
  /** Optional custom class name */
  className?: string
  /** List of active sessions */
  sessions: Session[]
  /** Current session ID */
  currentSessionId: string
  /** Callback to revoke a session */
  onRevokeSession?: (sessionId: string) => Promise<void>
  /** Callback to revoke all other sessions */
  onRevokeAllOthers?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Custom logo URL */
  logoUrl?: string
}

export function SessionManagement({
  className,
  sessions,
  currentSessionId,
  onRevokeSession,
  onRevokeAllOthers,
  onError,
  logoUrl,
}: SessionManagementProps) {
  const [revokingSessionId, setRevokingSessionId] = React.useState<string | null>(null)
  const [revokingAll, setRevokingAll] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleRevokeSession = async (sessionId: string) => {
    if (!onRevokeSession) return

    setRevokingSessionId(sessionId)
    setError(null)

    try {
      await onRevokeSession(sessionId)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to revoke session')
      setError(error.message)
      onError?.(error)
    } finally {
      setRevokingSessionId(null)
    }
  }

  const handleRevokeAllOthers = async () => {
    if (!onRevokeAllOthers) return

    setRevokingAll(true)
    setError(null)

    try {
      await onRevokeAllOthers()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to revoke sessions')
      setError(error.message)
      onError?.(error)
    } finally {
      setRevokingAll(false)
    }
  }

  const getDeviceIcon = (type: Session['device']['type']) => {
    switch (type) {
      case 'desktop':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        )
      case 'mobile':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
        )
      case 'tablet':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
        )
      default:
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        )
    }
  }

  const formatTimestamp = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString()
  }

  const otherSessions = sessions.filter((s) => s.id !== currentSessionId)

  return (
    <Card className={cn('w-full max-w-4xl mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-8" />
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Active Sessions</h2>
        <p className="text-sm text-muted-foreground mt-2">
          Manage your active sessions and sign out from devices you don't recognize
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Revoke All Others Button */}
      {otherSessions.length > 0 && onRevokeAllOthers && (
        <div className="mb-4">
          <Button
            variant="outline"
            onClick={handleRevokeAllOthers}
            disabled={revokingAll}
          >
            {revokingAll ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2"></div>
                Revoking...
              </>
            ) : (
              'Revoke all other sessions'
            )}
          </Button>
        </div>
      )}

      {/* Sessions List */}
      <div className="space-y-4">
        {sessions.map((session) => {
          const isCurrent = session.id === currentSessionId
          const isRevoking = revokingSessionId === session.id
          const hasWarnings = session.warnings && session.warnings.length > 0

          return (
            <div
              key={session.id}
              className={cn(
                'border rounded-lg p-4',
                isCurrent && 'border-primary bg-primary/5',
                hasWarnings && 'border-yellow-500 bg-yellow-50'
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3 flex-1">
                  {/* Device Icon */}
                  <div className={cn('mt-1', isCurrent ? 'text-primary' : 'text-muted-foreground')}>
                    {getDeviceIcon(session.device.type)}
                  </div>

                  {/* Session Info */}
                  <div className="flex-1 min-w-0">
                    {/* Device Name */}
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-sm">
                        {session.device.name}
                      </h3>
                      {isCurrent && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary text-primary-foreground">
                          Current Session
                        </span>
                      )}
                    </div>

                    {/* Device Details */}
                    <div className="text-sm text-muted-foreground space-y-1">
                      {session.device.os && session.device.browser && (
                        <p>
                          {session.device.browser} on {session.device.os}
                        </p>
                      )}
                      {session.location && (
                        <p>
                          {session.location.city && session.location.country
                            ? `${session.location.city}, ${session.location.country}`
                            : session.location.ip}
                        </p>
                      )}
                      <p>Last active {formatTimestamp(session.lastActiveAt)}</p>
                    </div>

                    {/* Warnings */}
                    {hasWarnings && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {session.warnings?.includes('unusual_location') && (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                            ⚠️ Unusual location
                          </span>
                        )}
                        {session.warnings?.includes('new_device') && (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                            ⚠️ New device
                          </span>
                        )}
                        {session.warnings?.includes('suspicious_activity') && (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">
                            🚨 Suspicious activity
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Revoke Button */}
                {!isCurrent && onRevokeSession && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRevokeSession(session.id)}
                    disabled={isRevoking}
                    className="ml-4"
                  >
                    {isRevoking ? (
                      <>
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-current mr-1"></div>
                        Revoking...
                      </>
                    ) : (
                      'Revoke'
                    )}
                  </Button>
                )}
              </div>
            </div>
          )
        })}

        {sessions.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <p>No active sessions found</p>
          </div>
        )}
      </div>

      {/* Security Info */}
      <div className="mt-6 bg-muted rounded-lg p-4">
        <h4 className="text-sm font-medium mb-2">Security Tips</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• If you see a session you don't recognize, revoke it immediately</li>
          <li>• Sessions expire automatically after a period of inactivity</li>
          <li>• Revoking a session will sign out that device</li>
          <li>• Your current session cannot be revoked from here</li>
        </ul>
      </div>
    </Card>
  )
}
