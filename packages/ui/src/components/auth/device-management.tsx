import * as React from 'react'
import { Button } from '../button'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export interface TrustedDevice {
  /** Unique device identifier */
  id: string
  /** Device fingerprint hash */
  fingerprint: string
  /** Device information */
  device: {
    type: 'desktop' | 'mobile' | 'tablet' | 'unknown'
    name: string
    os?: string
    browser?: string
  }
  /** Location when device was added */
  location?: {
    city?: string
    country?: string
    ip: string
  }
  /** Device trust status */
  isTrusted: boolean
  /** Timestamps */
  addedAt: Date
  lastUsedAt: Date
  /** Whether this is the current device */
  isCurrent?: boolean
  /** Notifications enabled for this device */
  notificationsEnabled?: boolean
}

export interface DeviceManagementProps {
  /** Optional custom class name */
  className?: string
  /** List of registered devices */
  devices: TrustedDevice[]
  /** Current device ID */
  currentDeviceId: string
  /** Callback to trust a device */
  onTrustDevice?: (deviceId: string) => Promise<void>
  /** Callback to revoke device trust */
  onRevokeDevice?: (deviceId: string) => Promise<void>
  /** Callback to toggle notifications */
  onToggleNotifications?: (deviceId: string, enabled: boolean) => Promise<void>
  /** Callback to remove a device */
  onRemoveDevice?: (deviceId: string) => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Custom logo URL */
  logoUrl?: string
  /** Show device fingerprints */
  showFingerprints?: boolean
}

export function DeviceManagement({
  className,
  devices,
  currentDeviceId,
  onTrustDevice,
  onRevokeDevice,
  onToggleNotifications,
  onRemoveDevice,
  onError,
  logoUrl,
  showFingerprints = false,
}: DeviceManagementProps) {
  const [loadingDeviceId, setLoadingDeviceId] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const handleTrustDevice = async (deviceId: string) => {
    if (!onTrustDevice) return

    setLoadingDeviceId(deviceId)
    setError(null)

    try {
      await onTrustDevice(deviceId)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to trust device')
      setError(error.message)
      onError?.(error)
    } finally {
      setLoadingDeviceId(null)
    }
  }

  const handleRevokeDevice = async (deviceId: string) => {
    if (!onRevokeDevice) return

    setLoadingDeviceId(deviceId)
    setError(null)

    try {
      await onRevokeDevice(deviceId)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to revoke device trust')
      setError(error.message)
      onError?.(error)
    } finally {
      setLoadingDeviceId(null)
    }
  }

  const handleToggleNotifications = async (deviceId: string, enabled: boolean) => {
    if (!onToggleNotifications) return

    setError(null)

    try {
      await onToggleNotifications(deviceId, enabled)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update notifications')
      setError(error.message)
      onError?.(error)
    }
  }

  const handleRemoveDevice = async (deviceId: string) => {
    if (!onRemoveDevice) return

    const confirmed = window.confirm(
      'Are you sure you want to remove this device? You will need to verify it again next time you sign in from this device.'
    )

    if (!confirmed) return

    setLoadingDeviceId(deviceId)
    setError(null)

    try {
      await onRemoveDevice(deviceId)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to remove device')
      setError(error.message)
      onError?.(error)
    } finally {
      setLoadingDeviceId(null)
    }
  }

  const getDeviceIcon = (type: TrustedDevice['device']['type']) => {
    switch (type) {
      case 'desktop':
        return (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
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

  const trustedDevices = devices.filter((d) => d.isTrusted)
  const untrustedDevices = devices.filter((d) => !d.isTrusted)

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
        <h2 className="text-2xl font-bold">Device Management</h2>
        <p className="text-sm text-muted-foreground mt-2">
          Manage your trusted devices and control which devices can access your account
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Trusted Devices Section */}
      {trustedDevices.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Trusted Devices ({trustedDevices.length})</h3>
          <div className="space-y-4">
            {trustedDevices.map((device) => {
              const isCurrent = device.id === currentDeviceId
              const isLoading = loadingDeviceId === device.id

              return (
                <div
                  key={device.id}
                  className={cn(
                    'border rounded-lg p-4',
                    isCurrent && 'border-primary bg-primary/5'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4 flex-1">
                      {/* Device Icon with Trust Badge */}
                      <div className="relative">
                        <div className={cn('mt-1', isCurrent ? 'text-primary' : 'text-muted-foreground')}>
                          {getDeviceIcon(device.device.type)}
                        </div>
                        <div className="absolute -bottom-1 -right-1 bg-green-500 rounded-full p-0.5">
                          <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </div>
                      </div>

                      {/* Device Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-sm">{device.device.name}</h4>
                          {isCurrent && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary text-primary-foreground">
                              Current Device
                            </span>
                          )}
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            Trusted
                          </span>
                        </div>

                        <div className="text-sm text-muted-foreground space-y-1">
                          {device.device.os && device.device.browser && (
                            <p>
                              {device.device.browser} on {device.device.os}
                            </p>
                          )}
                          {device.location && (
                            <p>
                              Added from{' '}
                              {device.location.city && device.location.country
                                ? `${device.location.city}, ${device.location.country}`
                                : device.location.ip}
                            </p>
                          )}
                          <p>Last used {formatTimestamp(device.lastUsedAt)}</p>
                          {showFingerprints && (
                            <p className="font-mono text-xs">
                              Fingerprint: {device.fingerprint.slice(0, 16)}...
                            </p>
                          )}
                        </div>

                        {/* Notification Toggle */}
                        {onToggleNotifications && (
                          <div className="mt-3 flex items-center">
                            <label className="flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={device.notificationsEnabled}
                                onChange={(e) =>
                                  handleToggleNotifications(device.id, e.target.checked)
                                }
                                className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
                              />
                              <span className="ml-2 text-sm text-muted-foreground">
                                Notify me of sign-ins from this device
                              </span>
                            </label>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="ml-4 flex flex-col gap-2">
                      {!isCurrent && onRevokeDevice && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRevokeDevice(device.id)}
                          disabled={isLoading}
                        >
                          {isLoading ? 'Processing...' : 'Revoke Trust'}
                        </Button>
                      )}
                      {!isCurrent && onRemoveDevice && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemoveDevice(device.id)}
                          disabled={isLoading}
                          className="text-destructive hover:text-destructive"
                        >
                          {isLoading ? 'Removing...' : 'Remove'}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Untrusted Devices Section */}
      {untrustedDevices.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-4">
            Unverified Devices ({untrustedDevices.length})
          </h3>
          <div className="space-y-4">
            {untrustedDevices.map((device) => {
              const isLoading = loadingDeviceId === device.id

              return (
                <div key={device.id} className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4 flex-1">
                      <div className="text-yellow-600 mt-1">
                        {getDeviceIcon(device.device.type)}
                      </div>

                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-sm">{device.device.name}</h4>
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-200 text-yellow-800">
                            Unverified
                          </span>
                        </div>

                        <div className="text-sm text-muted-foreground space-y-1">
                          {device.device.os && device.device.browser && (
                            <p>
                              {device.device.browser} on {device.device.os}
                            </p>
                          )}
                          {device.location && (
                            <p>
                              First seen in{' '}
                              {device.location.city && device.location.country
                                ? `${device.location.city}, ${device.location.country}`
                                : device.location.ip}
                            </p>
                          )}
                          <p>Added {formatTimestamp(device.addedAt)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="ml-4 flex flex-col gap-2">
                      {onTrustDevice && (
                        <Button
                          size="sm"
                          onClick={() => handleTrustDevice(device.id)}
                          disabled={isLoading}
                        >
                          {isLoading ? 'Processing...' : 'Trust Device'}
                        </Button>
                      )}
                      {onRemoveDevice && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemoveDevice(device.id)}
                          disabled={isLoading}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {devices.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>No devices registered</p>
          <p className="text-sm mt-2">Devices will appear here when you sign in from them</p>
        </div>
      )}

      {/* Info Section */}
      <div className="mt-6 bg-muted rounded-lg p-4">
        <h4 className="text-sm font-medium mb-2">About Device Trust</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• Trusted devices can skip additional verification steps</li>
          <li>• Device fingerprints help identify unique devices</li>
          <li>• Revoking trust requires re-verification on next sign-in</li>
          <li>• Remove devices you no longer use or recognize</li>
        </ul>
      </div>
    </Card>
  )
}
