import type { Meta, StoryObj } from '@storybook/react'
import * as React from 'react'
import { AuditLog } from './audit-log'

const meta = {
  title: 'Authentication/Security/AuditLog',
  component: AuditLog,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onLoadMore: { action: 'load more' },
    onExport: { action: 'export' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof AuditLog>

export default meta
type Story = StoryObj<typeof meta>

const sampleEvents = [
  {
    id: 'evt-1',
    type: 'auth.login' as const,
    category: 'auth' as const,
    actor: {
      id: 'user-1',
      email: 'john.doe@example.com',
      name: 'John Doe',
    },
    ipAddress: '192.168.1.1',
    location: {
      city: 'San Francisco',
      country: 'United States',
    },
    timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 minutes ago
    severity: 'info' as const,
  },
  {
    id: 'evt-2',
    type: 'security.suspicious_activity' as const,
    category: 'security' as const,
    actor: {
      id: 'user-2',
      email: 'jane.smith@example.com',
      name: 'Jane Smith',
    },
    ipAddress: '203.0.113.99',
    location: {
      city: 'Unknown',
      country: 'Russia',
    },
    timestamp: new Date(Date.now() - 1000 * 60 * 15), // 15 minutes ago
    severity: 'critical' as const,
    metadata: {
      reason: 'Multiple failed login attempts',
      attempts: 5,
    },
  },
  {
    id: 'evt-3',
    type: 'auth.mfa_enabled' as const,
    category: 'auth' as const,
    actor: {
      id: 'user-1',
      email: 'john.doe@example.com',
      name: 'John Doe',
    },
    ipAddress: '192.168.1.1',
    timestamp: new Date(Date.now() - 1000 * 60 * 60), // 1 hour ago
    severity: 'info' as const,
    metadata: {
      method: 'authenticator_app',
    },
  },
  {
    id: 'evt-4',
    type: 'admin.role_changed' as const,
    category: 'admin' as const,
    actor: {
      id: 'admin-1',
      email: 'admin@example.com',
      name: 'Admin User',
    },
    target: {
      id: 'user-3',
      email: 'bob.wilson@example.com',
      name: 'Bob Wilson',
      type: 'user',
    },
    ipAddress: '10.0.0.1',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    severity: 'warning' as const,
    metadata: {
      oldRole: 'user',
      newRole: 'admin',
    },
  },
  {
    id: 'evt-5',
    type: 'compliance.data_export' as const,
    category: 'compliance' as const,
    actor: {
      id: 'user-1',
      email: 'john.doe@example.com',
      name: 'John Doe',
    },
    ipAddress: '192.168.1.1',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    severity: 'info' as const,
    metadata: {
      format: 'json',
      dataTypes: ['profile', 'settings', 'activity'],
    },
  },
  {
    id: 'evt-6',
    type: 'auth.failed_login' as const,
    category: 'auth' as const,
    actor: {
      id: 'user-4',
      email: 'alice.jones@example.com',
      name: 'Alice Jones',
    },
    ipAddress: '172.16.0.1',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2), // 2 days ago
    severity: 'warning' as const,
    metadata: {
      reason: 'invalid_password',
    },
  },
  {
    id: 'evt-7',
    type: 'security.device_trusted' as const,
    category: 'security' as const,
    actor: {
      id: 'user-1',
      email: 'john.doe@example.com',
      name: 'John Doe',
    },
    ipAddress: '192.168.1.2',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3), // 3 days ago
    severity: 'info' as const,
    metadata: {
      deviceName: 'iPhone 15 Pro',
      fingerprint: 'a1b2c3d4e5f6',
    },
  },
]

export const Default: Story = {
  args: {
    events: sampleEvents,
  },
}

export const FilteredByAuth: Story = {
  args: {
    events: sampleEvents.filter((e) => e.category === 'auth'),
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Filtered to show only authentication events
      </p>
      <AuditLog {...args} />
    </div>
  ),
}

export const FilteredBySecurity: Story = {
  args: {
    events: sampleEvents.filter((e) => e.category === 'security'),
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Filtered to show only security events
      </p>
      <AuditLog {...args} />
    </div>
  ),
}

export const FilteredByCompliance: Story = {
  args: {
    events: sampleEvents.filter((e) => e.category === 'compliance'),
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Filtered to show only compliance events
      </p>
      <AuditLog {...args} />
    </div>
  ),
}

export const CriticalEventsOnly: Story = {
  args: {
    events: sampleEvents.filter((e) => e.severity === 'critical'),
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-red-50 border border-red-200 text-red-800 text-sm p-3 rounded-md max-w-md">
        🚨 <strong>Critical Events Only:</strong> Immediate attention required
      </div>
      <AuditLog {...args} />
    </div>
  ),
}

export const WarningEventsOnly: Story = {
  args: {
    events: sampleEvents.filter((e) => e.severity === 'warning'),
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm p-3 rounded-md max-w-md">
        ⚠️ <strong>Warning Events:</strong> Review recommended
      </div>
      <AuditLog {...args} />
    </div>
  ),
}

export const WithExport: Story = {
  args: {
    events: sampleEvents,
    showExport: true,
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Use the export buttons to download audit logs in CSV or JSON format
      </p>
      <AuditLog
        {...args}
        onExport={async (format, filters) => {
          await new Promise((resolve) => setTimeout(resolve, 1000))
          console.log('Exporting as', format, 'with filters', filters)
        }}
      />
    </div>
  ),
}

export const InteractiveLoadMore: Story = {
  args: {
    events: sampleEvents.slice(0, 3),
    hasMore: true,
  },
  render: (args) => {
    const [events, setEvents] = React.useState(args.events)
    const [hasMore, setHasMore] = React.useState(true)

    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground max-w-md">
          Click "Load More" to see pagination in action
        </p>
        <AuditLog
          events={events}
          hasMore={hasMore}
          onLoadMore={async () => {
            await new Promise((resolve) => setTimeout(resolve, 1000))
            setEvents([...events, ...sampleEvents.slice(events.length, events.length + 2)])
            if (events.length >= sampleEvents.length - 2) {
              setHasMore(false)
            }
          }}
        />
      </div>
    )
  },
}

export const EmptyState: Story = {
  args: {
    events: [],
  },
}

export const SecurityIncidentTimeline: Story = {
  args: {
    events: [
      {
        id: 'incident-1',
        type: 'security.suspicious_activity' as const,
        category: 'security' as const,
        actor: {
          id: 'attacker-1',
          email: 'suspicious@example.com',
        },
        ipAddress: '198.51.100.99',
        location: {
          city: 'Unknown',
          country: 'Unknown',
        },
        timestamp: new Date(Date.now() - 1000 * 60 * 10), // 10 minutes ago
        severity: 'critical' as const,
        metadata: {
          reason: 'Brute force attack detected',
          attempts: 50,
        },
      },
      {
        id: 'incident-2',
        type: 'auth.failed_login' as const,
        category: 'auth' as const,
        actor: {
          id: 'attacker-1',
          email: 'suspicious@example.com',
        },
        ipAddress: '198.51.100.99',
        timestamp: new Date(Date.now() - 1000 * 60 * 9), // 9 minutes ago
        severity: 'warning' as const,
      },
      {
        id: 'incident-3',
        type: 'security.session_revoked' as const,
        category: 'security' as const,
        actor: {
          id: 'admin-1',
          email: 'admin@example.com',
          name: 'Security Admin',
        },
        target: {
          id: 'attacker-1',
          email: 'suspicious@example.com',
          type: 'session',
        },
        ipAddress: '10.0.0.1',
        timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 minutes ago
        severity: 'warning' as const,
        metadata: {
          reason: 'Suspicious activity detected',
        },
      },
      {
        id: 'incident-4',
        type: 'admin.user_deleted' as const,
        category: 'admin' as const,
        actor: {
          id: 'admin-1',
          email: 'admin@example.com',
          name: 'Security Admin',
        },
        target: {
          id: 'attacker-1',
          email: 'suspicious@example.com',
          type: 'user',
        },
        ipAddress: '10.0.0.1',
        timestamp: new Date(Date.now() - 1000 * 60 * 2), // 2 minutes ago
        severity: 'critical' as const,
        metadata: {
          reason: 'Security threat - account terminated',
        },
      },
    ],
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-red-50 border border-red-200 text-red-800 text-sm p-3 rounded-md max-w-md">
        🚨 <strong>Security Incident Timeline:</strong> Brute force attack detected and
        neutralized
      </div>
      <AuditLog {...args} />
    </div>
  ),
}

export const ComplianceAudit: Story = {
  args: {
    events: [
      {
        id: 'comp-1',
        type: 'compliance.consent_granted' as const,
        category: 'compliance' as const,
        actor: {
          id: 'user-1',
          email: 'john.doe@example.com',
          name: 'John Doe',
        },
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30), // 30 days ago
        severity: 'info' as const,
        metadata: {
          consentType: 'data_processing',
          version: '1.0',
        },
      },
      {
        id: 'comp-2',
        type: 'compliance.data_export' as const,
        category: 'compliance' as const,
        actor: {
          id: 'user-1',
          email: 'john.doe@example.com',
          name: 'John Doe',
        },
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 15), // 15 days ago
        severity: 'info' as const,
        metadata: {
          format: 'json',
          dataTypes: ['profile', 'activity', 'settings'],
          requestedBy: 'user',
        },
      },
      {
        id: 'comp-3',
        type: 'compliance.consent_revoked' as const,
        category: 'compliance' as const,
        actor: {
          id: 'user-1',
          email: 'john.doe@example.com',
          name: 'John Doe',
        },
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7), // 7 days ago
        severity: 'warning' as const,
        metadata: {
          consentType: 'marketing',
        },
      },
      {
        id: 'comp-4',
        type: 'compliance.data_deletion' as const,
        category: 'compliance' as const,
        actor: {
          id: 'user-2',
          email: 'jane.smith@example.com',
          name: 'Jane Smith',
        },
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3), // 3 days ago
        severity: 'warning' as const,
        metadata: {
          deletedData: ['profile', 'activity_logs'],
          reason: 'GDPR right to erasure',
        },
      },
    ],
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 text-blue-800 text-sm p-3 rounded-md max-w-md">
        📋 <strong>Compliance Audit Trail:</strong> GDPR and data privacy events
      </div>
      <AuditLog {...args} showExport={true} />
    </div>
  ),
}

export const WithLogo: Story = {
  args: {
    events: sampleEvents,
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}
