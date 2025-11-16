import type { Meta, StoryObj } from '@storybook/react'
import { DeviceManagement } from './device-management'

const meta = {
  title: 'Authentication/Security/DeviceManagement',
  component: DeviceManagement,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onTrustDevice: { action: 'trust device' },
    onRevokeDevice: { action: 'revoke device' },
    onToggleNotifications: { action: 'toggle notifications' },
    onRemoveDevice: { action: 'remove device' },
    onError: { action: 'error' },
  },
} satisfies Meta<typeof DeviceManagement>

export default meta
type Story = StoryObj<typeof meta>

const sampleDevices = [
  {
    id: 'device-1',
    fingerprint: 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6',
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
    isTrusted: true,
    addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30), // 30 days ago
    lastUsedAt: new Date(Date.now() - 1000 * 30), // 30 seconds ago
    isCurrent: true,
    notificationsEnabled: true,
  },
  {
    id: 'device-2',
    fingerprint: 'b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7',
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
    isTrusted: true,
    addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 15), // 15 days ago
    lastUsedAt: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    notificationsEnabled: false,
  },
  {
    id: 'device-3',
    fingerprint: 'c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8',
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
    isTrusted: true,
    addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7), // 7 days ago
    lastUsedAt: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    notificationsEnabled: true,
  },
]

export const Default: Story = {
  args: {
    devices: sampleDevices,
    currentDeviceId: 'device-1',
  },
}

export const SingleDevice: Story = {
  args: {
    devices: [sampleDevices[0]],
    currentDeviceId: 'device-1',
  },
}

export const ManyDevices: Story = {
  args: {
    devices: [
      ...sampleDevices,
      {
        id: 'device-4',
        fingerprint: 'd4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9',
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
        isTrusted: true,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 60),
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30),
        notificationsEnabled: false,
      },
      {
        id: 'device-5',
        fingerprint: 'e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0',
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
        isTrusted: true,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 45),
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14),
        notificationsEnabled: true,
      },
    ],
    currentDeviceId: 'device-1',
  },
}

export const WithUntrustedDevices: Story = {
  args: {
    devices: [
      ...sampleDevices,
      {
        id: 'device-untrusted-1',
        fingerprint: 'f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1',
        device: {
          type: 'desktop' as const,
          name: 'Unknown Device',
          os: 'Linux',
          browser: 'Firefox',
        },
        location: {
          city: 'Seattle',
          country: 'United States',
          ip: '198.51.100.1',
        },
        isTrusted: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 30),
        notificationsEnabled: false,
      },
      {
        id: 'device-untrusted-2',
        fingerprint: 'g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
        device: {
          type: 'mobile' as const,
          name: 'Unknown Phone',
          os: 'Android',
          browser: 'Chrome',
        },
        location: {
          city: 'Miami',
          country: 'United States',
          ip: '203.0.113.99',
        },
        isTrusted: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 60), // 1 hour ago
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 60),
        notificationsEnabled: false,
      },
    ],
    currentDeviceId: 'device-1',
  },
}

export const NoDevices: Story = {
  args: {
    devices: [],
    currentDeviceId: '',
  },
}

export const WithFingerprints: Story = {
  args: {
    devices: sampleDevices,
    currentDeviceId: 'device-1',
    showFingerprints: true,
  },
}

export const WithLogo: Story = {
  args: {
    devices: sampleDevices,
    currentDeviceId: 'device-1',
    logoUrl: 'https://via.placeholder.com/150x40?text=Logo',
  },
}

export const InteractiveTrust: Story = {
  args: {
    devices: [
      ...sampleDevices,
      {
        id: 'device-new',
        fingerprint: 'h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3',
        device: {
          type: 'desktop' as const,
          name: 'New Laptop',
          os: 'macOS 14.0',
          browser: 'Safari',
        },
        location: {
          city: 'Boston',
          country: 'United States',
          ip: '192.0.2.1',
        },
        isTrusted: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 10),
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 10),
        notificationsEnabled: false,
      },
    ],
    currentDeviceId: 'device-1',
  },
  render: (args) => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground max-w-md">
        Click "Trust Device" to see the loading state and trust a device
      </p>
      <DeviceManagement
        {...args}
        onTrustDevice={async (deviceId) => {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          console.log('Trusted device:', deviceId)
        }}
        onRevokeDevice={async (deviceId) => {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          console.log('Revoked device trust:', deviceId)
        }}
        onToggleNotifications={async (deviceId, enabled) => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          console.log('Toggled notifications for device:', deviceId, enabled)
        }}
        onRemoveDevice={async (deviceId) => {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          console.log('Removed device:', deviceId)
        }}
      />
    </div>
  ),
}

export const SecurityReview: Story = {
  args: {
    devices: [
      ...sampleDevices,
      {
        id: 'suspicious-device',
        fingerprint: 'suspicious123456789',
        device: {
          type: 'unknown' as const,
          name: 'Suspicious Device',
          os: 'Unknown OS',
          browser: 'Unknown Browser',
        },
        location: {
          city: 'Unknown',
          country: 'Russia',
          ip: '198.51.100.99',
        },
        isTrusted: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 5),
        lastUsedAt: new Date(Date.now() - 1000 * 60 * 5),
        notificationsEnabled: false,
      },
    ],
    currentDeviceId: 'device-1',
  },
  render: (args) => (
    <div className="space-y-4">
      <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm p-3 rounded-md max-w-md">
        ⚠️ <strong>Security Notice:</strong> Review your devices and remove any you don't recognize.
      </div>
      <DeviceManagement {...args} />
    </div>
  ),
}
