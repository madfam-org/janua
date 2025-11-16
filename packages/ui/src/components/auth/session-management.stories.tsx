import type { Meta, StoryObj } from '@storybook/react'
import { SessionManagement } from './session-management'

const meta = {
  title: 'Authentication/Security/SessionManagement',
  component: SessionManagement,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onRevokeSession: { action: 'revoke session' },
    onRevokeAllOthers: { action: 'revoke all others' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof SessionManagement>

export default meta
type Story = StoryObj<typeof meta>

const sampleSessions = [
  {
    id: 'session-1',
    device: {
      type: 'desktop' as const,
      name: 'MacBook Pro',
      os: 'macOS 14.0',
      browser: 'Chrome 120',
    },
    location: {
      city: 'San Francisco',
      country: 'United States',
      ip: '192.168.1.1',
    },
    createdAt: new Date(Date.now() - 1000 * 60 * 5), // 5 minutes ago
    lastActiveAt: new Date(Date.now() - 1000 * 30), // 30 seconds ago
    isCurrent: true,
  },
  {
    id: 'session-2',
    device: {
      type: 'mobile' as const,
      name: 'iPhone 15 Pro',
      os: 'iOS 17.0',
      browser: 'Safari',
    },
    location: {
      city: 'San Francisco',
      country: 'United States',
      ip: '192.168.1.2',
    },
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    lastActiveAt: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
  },
  {
    id: 'session-3',
    device: {
      type: 'desktop' as const,
      name: 'Windows PC',
      os: 'Windows 11',
      browser: 'Edge 120',
    },
    location: {
      city: 'New York',
      country: 'United States',
      ip: '10.0.0.5',
    },
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    lastActiveAt: new Date(Date.now() - 1000 * 60 * 60 * 12), // 12 hours ago
  },
]

export const Default: Story = {
  args: {
    sessions: sampleSessions,
    currentSessionId: 'session-1',
  },
}

export const SingleSession: Story = {
  args: {
    sessions: [sampleSessions[0]],
    currentSessionId: 'session-1',
  },
}

export const ManySessions: Story = {
  args: {
    sessions: [
      ...sampleSessions,
      {
        id: 'session-4',
        device: {
          type: 'tablet' as const,
          name: 'iPad Pro',
          os: 'iPadOS 17.0',
          browser: 'Safari',
        },
        location: {
          city: 'Los Angeles',
          country: 'United States',
          ip: '172.16.0.1',
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 48),
        lastActiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24),
      },
      {
        id: 'session-5',
        device: {
          type: 'mobile' as const,
          name: 'Samsung Galaxy S24',
          os: 'Android 14',
          browser: 'Chrome',
        },
        location: {
          city: 'Chicago',
          country: 'United States',
          ip: '203.0.113.1',
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 72),
        lastActiveAt: new Date(Date.now() - 1000 * 60 * 60 * 48),
      },
    ],
    currentSessionId: 'session-1',
  },
}

export const WithWarnings: Story = {
  args: {
    sessions: [
      sampleSessions[0],
      {
        ...sampleSessions[1],
        warnings: ['new_device'],
      },
      {
        ...sampleSessions[2],
        warnings: ['unusual_location'],
      },
      {
        id: 'session-4',
        device: {
          type: 'desktop' as const,
          name: 'Unknown Device',
          os: 'Linux',
          browser: 'Firefox',
        },
        location: {
          city: 'Moscow',
          country: 'Russia',
          ip: '198.51.100.1',
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 10),
        lastActiveAt: new Date(Date.now() - 1000 * 60 * 5),
        warnings: ['suspicious_activity', 'unusual_location'],
      },
    ],
    currentSessionId: 'session-1',
  },
}

export const NoSessions: Story = {
  args: {
    sessions: [],
    currentSessionId: '',
  },
}

export const WithLogo: Story = {
  args: {
    sessions: sampleSessions,
    currentSessionId: 'session-1',
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const InteractiveRevoke: Story = {
  args: {
    sessions: sampleSessions,
    currentSessionId: 'session-1',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Click "Revoke" on any session to see the loading state
      </p>
      <SessionManagement
        {...args}
        onRevokeSession={async (sessionId) => {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          console.log('Revoked session:', sessionId)
        }}
        onRevokeAllOthers={async () => {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          console.log('Revoked all other sessions')
        }}
      />
    </div>
  ),
}

export const SecurityAlert: Story = {
  args: {
    sessions: [
      sampleSessions[0],
      {
        id: 'session-suspicious',
        device: {
          type: 'unknown' as const,
          name: 'Unknown Device',
          os: 'Unknown OS',
          browser: 'Unknown Browser',
        },
        location: {
          city: 'Unknown',
          country: 'Unknown',
          ip: '203.0.113.99',
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 2),
        lastActiveAt: new Date(Date.now() - 1000 * 60),
        warnings: ['suspicious_activity', 'unusual_location', 'new_device'],
      },
    ],
    currentSessionId: 'session-1',
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-red-50 border border-red-200 text-red-800 text-sm p-3 rounded-md max-w-md">
        🚨 <strong>Security Alert:</strong> Suspicious activity detected. Review your sessions immediately.
      </div>
      <SessionManagement {...args} />
    </div>
  ),
}
