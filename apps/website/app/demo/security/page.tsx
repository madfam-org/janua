'use client'

import { SessionManagement, DeviceManagement } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import { useState } from 'react'

export default function SecurityShowcase() {
  const [sessionRevoked, setSessionRevoked] = useState(false)
  const [deviceTrusted, setDeviceTrusted] = useState(false)

  // Sample session data
  const sampleSessions = [
    {
      id: '1',
      device: {
        type: 'desktop' as const,
        name: 'MacBook Pro',
        os: 'macOS 14.0',
        browser: 'Chrome 120',
      },
      location: {
        city: 'San Francisco',
        country: 'USA',
        ip: '192.168.1.100',
      },
      createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
      lastActiveAt: new Date(Date.now() - 5 * 60 * 1000),
      isCurrent: true,
    },
    {
      id: '2',
      device: {
        type: 'mobile' as const,
        name: 'iPhone 15',
        os: 'iOS 17',
        browser: 'Safari Mobile',
      },
      location: {
        city: 'San Francisco',
        country: 'USA',
        ip: '192.168.1.101',
      },
      createdAt: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000),
      lastActiveAt: new Date(Date.now() - 2 * 60 * 60 * 1000),
      isCurrent: false,
    },
    {
      id: '3',
      device: {
        type: 'tablet' as const,
        name: 'iPad Pro',
        os: 'iPadOS 17',
        browser: 'Safari 17',
      },
      location: {
        city: 'Oakland',
        country: 'USA',
        ip: '10.0.0.50',
      },
      createdAt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      lastActiveAt: new Date(Date.now() - 24 * 60 * 60 * 1000),
      isCurrent: false,
    },
  ]

  // Sample device data
  const sampleDevices = [
    {
      id: '1',
      fingerprint: 'fp_abc123',
      device: {
        type: 'desktop' as const,
        name: 'MacBook Pro',
        os: 'macOS 14.0',
        browser: 'Chrome 120',
      },
      isTrusted: true,
      addedAt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      lastUsedAt: new Date(Date.now() - 5 * 60 * 1000),
    },
    {
      id: '2',
      fingerprint: 'fp_def456',
      device: {
        type: 'mobile' as const,
        name: 'iPhone 15',
        os: 'iOS 17.2',
        browser: 'Safari Mobile',
      },
      isTrusted: true,
      addedAt: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000),
      lastUsedAt: new Date(Date.now() - 2 * 60 * 60 * 1000),
    },
    {
      id: '3',
      fingerprint: 'fp_xyz789',
      device: {
        type: 'desktop' as const,
        name: 'Unknown Device',
        os: 'Windows 11',
        browser: 'Edge 119',
      },
      isTrusted: false,
      addedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
      lastUsedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    },
  ]

  const handleSessionRevoke = (sessionId: string) => {
    setSessionRevoked(true)
    // removed console.log
    setTimeout(() => setSessionRevoked(false), 3000)
  }

  const handleDeviceTrust = (deviceId: string, trusted: boolean) => {
    setDeviceTrusted(true)
    // removed console.log
    setTimeout(() => setDeviceTrusted(false), 3000)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Security Management
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Advanced security components for session tracking, device management, and suspicious activity monitoring.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Components</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <strong>SessionManagement</strong>: Active sessions</li>
              <li>• <strong>DeviceManagement</strong>: Device trust</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Multi-session tracking</li>
              <li>• Device fingerprinting</li>
              <li>• Location detection</li>
              <li>• Suspicious activity alerts</li>
              <li>• Bulk revocation</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Security</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Real-time session monitoring</li>
              <li>• Device trust management</li>
              <li>• IP-based detection</li>
              <li>• Anomaly notifications</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {sessionRevoked && (
        <div className="mb-6 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200">
          <p className="font-medium">✅ Session revoked successfully!</p>
        </div>
      )}

      {deviceTrusted && (
        <div className="mb-6 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200">
          <p className="font-medium">✅ Device trust status updated!</p>
        </div>
      )}

      {/* Live Component Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
          Live Component Demos
        </h3>

        <Tabs defaultValue="sessions" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="sessions">Session Management</TabsTrigger>
            <TabsTrigger value="devices">Device Management</TabsTrigger>
          </TabsList>

          <TabsContent value="sessions" className="mt-6">
            <SessionManagement
              sessions={sampleSessions}
              currentSessionId="1"
              onRevokeSession={async (sessionId: string) => {
                // removed console.log
                setSessionRevoked(true)
              }}
              onRevokeAllOthers={async () => {
                // removed console.log
                setSessionRevoked(true)
              }}
            />
            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Demo:</strong> View all active sessions with device info, location, and last activity.
                Revoke individual sessions or all sessions at once for security.
              </p>
            </div>
          </TabsContent>

          <TabsContent value="devices" className="mt-6">
            <DeviceManagement
              devices={sampleDevices}
              currentDeviceId="1"
              onTrustDevice={async (deviceId: string) => {
                // removed console.log
                setDeviceTrusted(true)
              }}
              onRevokeDevice={async (deviceId: string) => {
                // removed console.log
                setDeviceTrusted(true)
              }}
            />
            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Demo:</strong> Manage trusted devices, track device fingerprints, and control
                device-level access. Mark devices as trusted to skip MFA on future logins.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Implementation Examples */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Implementation Examples
        </h3>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Session Management with API</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { SessionManagement } from '@janua/ui'
import { useEffect, useState } from 'react'

export default function SessionsPage() {
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    // Fetch active sessions from API
    fetch('/api/sessions')
      .then(res => res.json())
      .then(data => setSessions(data.sessions))
  }, [])

  const handleRevoke = async (sessionId: string) => {
    // Revoke session via API
    await fetch(\`/api/sessions/\${sessionId}\`, {
      method: 'DELETE'
    })

    // Update UI
    setSessions(prev => prev.filter(s => s.id !== sessionId))
  }

  return (
    <SessionManagement
      sessions={sessions}
      onRevoke={handleRevoke}
      onRevokeAll={async (sessionIds) => {
        await Promise.all(
          sessionIds.map(id =>
            fetch(\`/api/sessions/\${id}\`, { method: 'DELETE' })
          )
        )
        setSessions([])
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Device Management with Trust</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`import { DeviceManagement } from '@janua/ui'

<DeviceManagement
  devices={devices}
  onTrust={async (deviceId, trusted) => {
    // Update device trust status
    await fetch(\`/api/devices/\${deviceId}/trust\`, {
      method: 'PATCH',
      body: JSON.stringify({ trusted })
    })

    // If trusted, skip MFA on this device
    if (trusted) {
      await updateMFAPolicy(deviceId, 'skip')
    }
  }}
  onRemove={async (deviceId) => {
    // Remove device and invalidate sessions
    await fetch(\`/api/devices/\${deviceId}\`, {
      method: 'DELETE'
    })

    // Revoke all sessions from this device
    await revokeDeviceSessions(deviceId)
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Suspicious Activity Detection</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`// Server-side session monitoring
async function detectSuspiciousActivity(session) {
  const checks = [
    // Check for location change
    await detectLocationAnomaly(session),

    // Check for unusual time
    await detectTimeAnomaly(session),

    // Check for new device
    await detectNewDevice(session),

    // Check for IP reputation
    await checkIPReputation(session.ipAddress)
  ]

  if (checks.some(check => check.suspicious)) {
    // Flag session as suspicious
    await flagSession(session.id, {
      reason: checks.find(c => c.suspicious).reason,
      severity: 'high'
    })

    // Notify user
    await sendSecurityAlert(session.userId, {
      type: 'suspicious_activity',
      session: session
    })

    // Optionally: Force re-authentication
    if (checks.some(c => c.severity === 'critical')) {
      await revokeSession(session.id)
    }
  }
}`}
            </pre>
          </div>
        </div>
      </div>

      {/* Component Specifications */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Component Specifications
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">SessionManagement (~420 LOC)</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Multi-session display with sorting</li>
              <li>• Current session highlighting</li>
              <li>• Device/browser/OS detection</li>
              <li>• IP address and location tracking</li>
              <li>• Individual and bulk revocation</li>
              <li>• Last active timestamp</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">DeviceManagement (~470 LOC)</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Device fingerprinting support</li>
              <li>• Trust status management</li>
              <li>• Device type icons (desktop/mobile)</li>
              <li>• Last seen tracking</li>
              <li>• Device removal with confirmation</li>
              <li>• Notification preferences</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Security Best Practices */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Security Best Practices
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Session Security</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Use secure, httpOnly session cookies</li>
              <li>✓ Implement session timeout (15-30 min)</li>
              <li>✓ Rotate session IDs after authentication</li>
              <li>✓ Store minimal data in session</li>
              <li>✓ Log all session events</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Device Trust</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Use device fingerprinting libraries</li>
              <li>✓ Store device trust in encrypted DB</li>
              <li>✓ Expire trust after 30-90 days</li>
              <li>✓ Re-verify on suspicious activity</li>
              <li>✓ Allow user to manage trust manually</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Anomaly Detection</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Monitor for location changes</li>
              <li>✓ Detect impossible travel patterns</li>
              <li>✓ Check for unusual login times</li>
              <li>✓ Flag new device logins</li>
              <li>✓ Analyze IP reputation</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Notifications</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Email alerts for new devices</li>
              <li>✓ Push notifications for suspicious activity</li>
              <li>✓ SMS for critical security events</li>
              <li>✓ In-app security dashboard</li>
              <li>✓ Allow users to report issues</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Enterprise Features */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Enterprise Security Features
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Advanced Monitoring</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              Real-time security dashboard with:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Live session activity feed</li>
              <li>• Geographic session map</li>
              <li>• Suspicious activity alerts</li>
              <li>• Session analytics and trends</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Policy Enforcement</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              Automated security policies:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Max concurrent sessions limit</li>
              <li>• Geographic restrictions</li>
              <li>• Device type allowlists</li>
              <li>• Time-based access controls</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
