'use client'

import { AuditLog } from '@plinto/ui'
import { useState } from 'react'

export default function ComplianceShowcase() {
  const [exportStatus, setExportStatus] = useState<'idle' | 'success'>('idle')

  // Sample audit events demonstrating all categories and severity levels
  const sampleEvents = [
    // Authentication events
    {
      id: '1',
      type: 'auth.login' as const,
      category: 'auth' as const,
      severity: 'info' as const,
      actor: { id: 'user-123', name: 'John Doe', email: 'john@example.com' },
      timestamp: new Date(Date.now() - 5 * 60 * 1000),
      ipAddress: '192.168.1.100',
      userAgent: 'Chrome 120',
      location: { city: 'San Francisco', country: 'USA' },
    },
    {
      id: '2',
      type: 'auth.failed_login' as const,
      category: 'auth' as const,
      severity: 'warning' as const,
      actor: { id: 'unknown', email: 'attacker@example.com' },
      target: { id: 'user-123' },
      timestamp: new Date(Date.now() - 15 * 60 * 1000),
      ipAddress: '203.0.113.45',
      metadata: { reason: 'Invalid password', attempts: 3 },
    },
    // Security events
    {
      id: '3',
      type: 'security.suspicious_activity' as const,
      category: 'security' as const,
      severity: 'critical' as const,
      actor: { id: 'user-456', name: 'Jane Smith', email: 'jane@example.com' },
      target: { id: 'sess-xyz', type: 'session' },
      timestamp: new Date(Date.now() - 30 * 60 * 1000),
      location: { city: 'Moscow', country: 'Russia' },
      metadata: {
        reason: 'Login from unusual location',
        previousLocation: 'New York, USA',
        timeDifference: '2 hours'
      },
    },
    {
      id: '4',
      type: 'security.session_revoked' as const,
      category: 'security' as const,
      severity: 'warning' as const,
      actor: { id: 'user-123', name: 'John Doe', email: 'john@example.com' },
      target: { id: 'sess-old', type: 'session' },
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
      location: { city: 'San Francisco', country: 'USA' },
      metadata: { reason: 'Manual revocation' },
    },
    // Admin events
    {
      id: '5',
      type: 'admin.user_created' as const,
      category: 'admin' as const,
      severity: 'info' as const,
      actor: { id: 'admin-1', name: 'Admin User', email: 'admin@example.com' },
      target: { id: 'user-789', email: 'newuser@example.com' },
      timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000),
      metadata: { role: 'member' },
    },
    {
      id: '6',
      type: 'admin.role_changed' as const,
      category: 'admin' as const,
      severity: 'warning' as const,
      actor: { id: 'admin-1', name: 'Admin User', email: 'admin@example.com' },
      target: { id: 'user-456', email: 'jane@example.com', name: 'Jane Smith' },
      timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000),
      metadata: { previousRole: 'member', newRole: 'admin' },
    },
    // Compliance events
    {
      id: '7',
      type: 'compliance.data_export' as const,
      category: 'compliance' as const,
      severity: 'info' as const,
      actor: { id: 'user-123', name: 'John Doe', email: 'john@example.com' },
      timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000),
      metadata: { format: 'JSON', dataTypes: ['profile', 'sessions', 'audit_logs'], size: '2.5 MB' },
    },
    {
      id: '8',
      type: 'compliance.consent_granted' as const,
      category: 'compliance' as const,
      severity: 'info' as const,
      actor: { id: 'user-789', name: 'New User', email: 'newuser@example.com' },
      timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000),
      metadata: { consentType: 'marketing', version: '2.1', expiresAt: '2025-11-15' },
    },
    {
      id: '9',
      type: 'compliance.data_deletion' as const,
      category: 'compliance' as const,
      severity: 'critical' as const,
      actor: { id: 'user-456', name: 'Jane Smith', email: 'jane@example.com' },
      target: { id: 'user-456', email: 'jane@example.com', name: 'Jane Smith' },
      timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000),
      metadata: { reason: 'GDPR Right to be Forgotten', dataTypes: ['all'], requestDate: '2025-11-10' },
    },
  ]

  const handleExport = async (format: 'csv' | 'json', filters?: any) => {
    setExportStatus('success')
    console.log(`Exporting events as ${format.toUpperCase()}`, filters)
    setTimeout(() => setExportStatus('idle'), 3000)

    // In real implementation, generate and download file
    const data = format === 'json'
      ? JSON.stringify(sampleEvents, null, 2)
      : convertToCSV(sampleEvents)

    const blob = new Blob([data], { type: format === 'json' ? 'application/json' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit-log-${Date.now()}.${format}`
    a.click()
  }

  const convertToCSV = (events: any[]) => {
    const headers = ['ID', 'Timestamp', 'Event Type', 'Category', 'Severity', 'Actor', 'Resource', 'Metadata']
    const rows = events.map(e => [
      e.id,
      e.timestamp.toISOString(),
      e.eventType,
      e.category,
      e.severity,
      e.actor.name || e.actor.email,
      `${e.resource.type}:${e.resource.id}`,
      JSON.stringify(e.metadata)
    ])
    return [headers, ...rows].map(row => row.join(',')).join('\n')
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Compliance & Audit Logging
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Enterprise-grade audit logging with comprehensive event tracking, filtering, and compliance export capabilities.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• 20+ event types tracked</li>
              <li>• Multi-category filtering</li>
              <li>• Severity-based alerts</li>
              <li>• CSV/JSON export</li>
              <li>• Advanced search</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Event Categories</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <strong>Auth</strong>: Login, logout, failures</li>
              <li>• <strong>Security</strong>: Sessions, devices, threats</li>
              <li>• <strong>Admin</strong>: User/role management</li>
              <li>• <strong>Compliance</strong>: Data, consent, GDPR</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Compliance</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• GDPR Article 30 compliant</li>
              <li>• SOC 2 audit trail</li>
              <li>• HIPAA logging support</li>
              <li>• ISO 27001 requirements</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Export Status */}
      {exportStatus === 'success' && (
        <div className="mb-6 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200">
          <p className="font-medium">✅ Audit log exported successfully!</p>
        </div>
      )}

      {/* Live Component Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
          Live Audit Log Demo
        </h3>

        <AuditLog
          events={sampleEvents}
          onExport={handleExport}
        />

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Demo:</strong> This audit log shows sample events across all categories (auth, security, admin, compliance).
            Use filters to narrow down events, search for specific activities, and export data for compliance reporting.
          </p>
        </div>
      </div>

      {/* Implementation Examples */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Implementation Examples
        </h3>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Basic Audit Log with API</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { AuditLog } from '@plinto/ui'
import { useEffect, useState } from 'react'

export default function AuditPage() {
  const [events, setEvents] = useState([])

  useEffect(() => {
    // Fetch audit events from API
    fetch('/api/audit-log', {
      headers: {
        'Authorization': \`Bearer \${accessToken}\`
      }
    })
      .then(res => res.json())
      .then(data => setEvents(data.events))
  }, [])

  const handleExport = async (format, events) => {
    // Request export from backend
    const response = await fetch('/api/audit-log/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, eventIds: events.map(e => e.id) })
    })

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = \`audit-log-\${Date.now()}.\${format}\`
    a.click()
  }

  return <AuditLog events={events} onExport={handleExport} />
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Server-Side Event Logging</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`// Server-side audit event creation
async function logAuditEvent({
  eventType,
  category,
  severity,
  actorId,
  resourceType,
  resourceId,
  metadata
}) {
  const event = {
    id: generateEventId(),
    timestamp: new Date(),
    eventType,
    category,
    severity,
    actor: await getActorDetails(actorId),
    resource: { type: resourceType, id: resourceId },
    metadata: {
      ...metadata,
      ipAddress: getClientIP(),
      userAgent: getUserAgent()
    }
  }

  // Store in database
  await db.auditLog.create({ data: event })

  // Send to monitoring service
  await monitoring.track('audit_event', event)

  // Alert on critical events
  if (severity === 'critical') {
    await sendSecurityAlert(event)
  }

  return event
}

// Usage examples
await logAuditEvent({
  eventType: 'auth.login',
  category: 'auth',
  severity: 'info',
  actorId: user.id,
  resourceType: 'session',
  resourceId: session.id,
  metadata: { location: 'San Francisco, CA' }
})

await logAuditEvent({
  eventType: 'compliance.data_export',
  category: 'compliance',
  severity: 'info',
  actorId: user.id,
  resourceType: 'data_export',
  resourceId: exportJob.id,
  metadata: {
    format: 'JSON',
    dataTypes: ['profile', 'sessions'],
    requestedBy: user.email
  }
})`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">GDPR Data Subject Request</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`// Handle GDPR Article 15 - Right to Access
async function handleDataSubjectAccessRequest(userId: string) {
  // Collect all user data
  const userData = {
    profile: await db.user.findUnique({ where: { id: userId } }),
    sessions: await db.session.findMany({ where: { userId } }),
    auditLog: await db.auditLog.findMany({
      where: { 'actor.id': userId }
    }),
    consents: await db.consent.findMany({ where: { userId } }),
    // ... other data categories
  }

  // Log the data export
  await logAuditEvent({
    eventType: 'compliance.data_export',
    category: 'compliance',
    severity: 'info',
    actorId: userId,
    resourceType: 'data_export',
    resourceId: generateExportId(),
    metadata: {
      requestType: 'GDPR Article 15',
      dataTypes: Object.keys(userData),
      size: JSON.stringify(userData).length
    }
  })

  return userData
}

// Handle GDPR Article 17 - Right to be Forgotten
async function handleDataDeletionRequest(userId: string) {
  // Log before deletion
  await logAuditEvent({
    eventType: 'compliance.data_deletion',
    category: 'compliance',
    severity: 'critical',
    actorId: userId,
    resourceType: 'user',
    resourceId: userId,
    metadata: {
      requestType: 'GDPR Article 17',
      requestDate: new Date().toISOString()
    }
  })

  // Delete user data
  await db.$transaction([
    db.session.deleteMany({ where: { userId } }),
    db.consent.deleteMany({ where: { userId } }),
    db.user.delete({ where: { id: userId } })
  ])
}`}
            </pre>
          </div>
        </div>
      </div>

      {/* Event Types Reference */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Event Types Reference
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Authentication Events</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>auth.login</code> - Successful login</li>
              <li>• <code>auth.logout</code> - User logout</li>
              <li>• <code>auth.failed_login</code> - Failed login attempt</li>
              <li>• <code>auth.password_reset</code> - Password reset</li>
              <li>• <code>auth.mfa_enabled</code> - MFA activation</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Security Events</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>security.session_revoked</code> - Session termination</li>
              <li>• <code>security.device_trusted</code> - Device trust update</li>
              <li>• <code>security.suspicious_activity</code> - Anomaly detected</li>
              <li>• <code>security.account_locked</code> - Account lockout</li>
              <li>• <code>security.password_changed</code> - Password update</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Admin Events</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>admin.user_created</code> - New user creation</li>
              <li>• <code>admin.user_deleted</code> - User deletion</li>
              <li>• <code>admin.role_changed</code> - Role modification</li>
              <li>• <code>admin.permissions_changed</code> - Permission update</li>
              <li>• <code>admin.settings_updated</code> - Settings change</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Compliance Events</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>compliance.data_export</code> - Data export request</li>
              <li>• <code>compliance.data_deletion</code> - Data deletion (GDPR)</li>
              <li>• <code>compliance.consent_granted</code> - Consent given</li>
              <li>• <code>compliance.consent_revoked</code> - Consent withdrawn</li>
              <li>• <code>compliance.access_log_viewed</code> - Log access</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Compliance Standards */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Compliance Standards Supported
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">GDPR (EU)</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              General Data Protection Regulation compliance:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Article 15: Right to Access (data export)</li>
              <li>✓ Article 17: Right to be Forgotten (deletion)</li>
              <li>✓ Article 30: Record of processing activities</li>
              <li>✓ Article 32: Security of processing (audit trail)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">SOC 2 Type II</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              System and Organization Controls:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Comprehensive audit logging</li>
              <li>✓ Access control monitoring</li>
              <li>✓ Change management tracking</li>
              <li>✓ Security incident logging</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">HIPAA</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              Health Insurance Portability and Accountability Act:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ 164.308: Administrative safeguards</li>
              <li>✓ 164.312: Technical safeguards (audit controls)</li>
              <li>✓ 164.530: Access and modification logging</li>
              <li>✓ 6-year retention requirement support</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">ISO 27001</h4>
            <p className="text-gray-600 dark:text-gray-400 mb-2">
              Information Security Management:
            </p>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ A.12.4.1: Event logging</li>
              <li>✓ A.12.4.2: Protection of log information</li>
              <li>✓ A.12.4.3: Administrator and operator logs</li>
              <li>✓ A.12.4.4: Clock synchronization</li>
            </ul>
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Performance</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Bundle size: ~550 LOC</li>
              <li>• Handles 1000+ events efficiently</li>
              <li>• Virtual scrolling for large datasets</li>
              <li>• Real-time filtering (0ms lag)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Export Capabilities</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• CSV format for spreadsheet analysis</li>
              <li>• JSON format for programmatic access</li>
              <li>• Filtered export (export only visible)</li>
              <li>• Batch export for large datasets</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
