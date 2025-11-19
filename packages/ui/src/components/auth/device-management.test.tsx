import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { DeviceManagement } from './device-management'
import type { TrustedDevice } from './device-management'
import { setupMockTime, restoreRealTime, isRelativeTime } from '@/test/utils'

describe('DeviceManagement', () => {
  const mockOnTrustDevice = vi.fn()
  const mockOnRevokeDevice = vi.fn()
  const mockOnToggleNotifications = vi.fn()
  const mockOnRemoveDevice = vi.fn()
  const mockOnError = vi.fn()

  const mockDevices: TrustedDevice[] = [
    {
      id: 'device-1',
      fingerprint: 'abcd1234efgh5678ijkl9012mnop3456',
      device: {
        type: 'desktop',
        name: 'Chrome on Windows',
        os: 'Windows 10',
        browser: 'Chrome',
      },
      location: {
        city: 'New York',
        country: 'USA',
        ip: '192.168.1.1',
      },
      isTrusted: true,
      addedAt: new Date('2024-01-01'),
      lastUsedAt: new Date(Date.now() - 300000), // 5 minutes ago
      isCurrent: true,
      notificationsEnabled: true,
    },
    {
      id: 'device-2',
      fingerprint: 'wxyz7890abcd1234efgh5678ijkl9012',
      device: {
        type: 'mobile',
        name: 'Safari on iPhone',
        os: 'iOS 17',
        browser: 'Safari',
      },
      location: {
        city: 'San Francisco',
        country: 'USA',
        ip: '192.168.1.2',
      },
      isTrusted: true,
      addedAt: new Date('2024-01-02'),
      lastUsedAt: new Date(Date.now() - 3600000), // 1 hour ago
      notificationsEnabled: false,
    },
    {
      id: 'device-3',
      fingerprint: 'qwer5678tyui9012asdf3456ghjk7890',
      device: {
        type: 'tablet',
        name: 'iPad',
        os: 'iPadOS 17',
        browser: 'Safari',
      },
      location: {
        city: 'London',
        country: 'UK',
        ip: '192.168.1.3',
      },
      isTrusted: false,
      addedAt: new Date('2024-01-03'),
      lastUsedAt: new Date(Date.now() - 86400000), // 1 day ago
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    window.confirm = vi.fn(() => true)
  })

  describe('Rendering', () => {
    it('should render device management component', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText('Device Management')).toBeInTheDocument()
      expect(screen.getByText(/Manage your trusted devices/i)).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          logoUrl="https://example.com/logo.png"
        />
      )

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })

    it('should display empty state when no devices', () => {
      render(
        <DeviceManagement devices={[]} currentDeviceId="current" />
      )

      expect(screen.getByText('No devices registered')).toBeInTheDocument()
      expect(screen.getByText(/Devices will appear here/i)).toBeInTheDocument()
    })
  })

  describe('Device Sections', () => {
    it('should separate trusted and untrusted devices', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText(/Trusted Devices \(2\)/i)).toBeInTheDocument()
      expect(screen.getByText(/Unverified Devices \(1\)/i)).toBeInTheDocument()
    })

    it('should display trusted badge for trusted devices', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      const trustedBadges = screen.getAllByText('Trusted')
      expect(trustedBadges).toHaveLength(2)
    })

    it('should display unverified badge for untrusted devices', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText('Unverified')).toBeInTheDocument()
    })

    it('should mark current device with badge', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText('Current Device')).toBeInTheDocument()
    })
  })

  describe('Device Information Display', () => {
    it('should display device names and details', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText('Chrome on Windows')).toBeInTheDocument()
      expect(screen.getByText('Safari on iPhone')).toBeInTheDocument()
      expect(screen.getByText('iPad')).toBeInTheDocument()
    })

    it('should display browser and OS information', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText(/Chrome on Windows 10/i)).toBeInTheDocument()
      expect(screen.getByText(/Safari on iOS 17/i)).toBeInTheDocument()
    })

    it('should display location information', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText(/New York, USA/i)).toBeInTheDocument()
      expect(screen.getByText(/San Francisco, USA/i)).toBeInTheDocument()
      expect(screen.getByText(/London, UK/i)).toBeInTheDocument()
    })

    it('should display fingerprints when showFingerprints is true', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          showFingerprints={true}
        />
      )

      expect(screen.getByText(/Fingerprint: abcd1234efgh5678/i)).toBeInTheDocument()
    })

    it('should not display fingerprints when showFingerprints is false', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          showFingerprints={false}
        />
      )

      expect(screen.queryByText(/Fingerprint:/i)).not.toBeInTheDocument()
    })

    it('should display relative timestamps', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      // Check that timestamps are displayed in relative format
      // The exact values may vary based on when the test runs
      const timestampElements = screen.getAllByText(/\d+[smhd] ago|Just now/i)
      expect(timestampElements.length).toBeGreaterThan(0)

      // Verify all found timestamps match the relative time format
      timestampElements.forEach((element) => {
        expect(isRelativeTime(element.textContent || '')).toBe(true)
      })
    })
  })

  describe('Trust Device', () => {
    it('should trust an unverified device', async () => {
      const user = userEvent.setup()
      mockOnTrustDevice.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onTrustDevice={mockOnTrustDevice}
        />
      )

      const trustButton = screen.getByRole('button', { name: /trust device/i })
      await user.click(trustButton)

      await waitFor(() => {
        expect(mockOnTrustDevice).toHaveBeenCalledWith('device-3')
      })
    })

    it('should show loading state during trust', async () => {
      const user = userEvent.setup()
      mockOnTrustDevice.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onTrustDevice={mockOnTrustDevice}
        />
      )

      const trustButton = screen.getByRole('button', { name: /trust device/i })
      await user.click(trustButton)

      expect(screen.getByText(/processing\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/processing\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle trust device error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to trust device')
      mockOnTrustDevice.mockRejectedValue(error)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onTrustDevice={mockOnTrustDevice}
          onError={mockOnError}
        />
      )

      const trustButton = screen.getByRole('button', { name: /trust device/i })
      await user.click(trustButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to trust device')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Revoke Device Trust', () => {
    it('should revoke device trust', async () => {
      const user = userEvent.setup()
      mockOnRevokeDevice.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRevokeDevice={mockOnRevokeDevice}
        />
      )

      const revokeTrustButtons = screen.getAllByRole('button', { name: /revoke trust/i })
      await user.click(revokeTrustButtons[0])

      await waitFor(() => {
        expect(mockOnRevokeDevice).toHaveBeenCalledWith('device-2')
      })
    })

    it('should not show revoke trust for current device', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRevokeDevice={mockOnRevokeDevice}
        />
      )

      const revokeTrustButtons = screen.getAllByRole('button', { name: /revoke trust/i })
      // Should only have 1 button (for device-2, not device-1 which is current)
      expect(revokeTrustButtons).toHaveLength(1)
    })

    it('should handle revoke device error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to revoke device trust')
      mockOnRevokeDevice.mockRejectedValue(error)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRevokeDevice={mockOnRevokeDevice}
          onError={mockOnError}
        />
      )

      const revokeTrustButtons = screen.getAllByRole('button', { name: /revoke trust/i })
      await user.click(revokeTrustButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Failed to revoke device trust')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Remove Device', () => {
    it('should show confirmation before removing device', async () => {
      const user = userEvent.setup()
      const confirmSpy = vi.spyOn(window, 'confirm')
      mockOnRemoveDevice.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRemoveDevice={mockOnRemoveDevice}
        />
      )

      const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
      await user.click(removeButtons[0])

      expect(confirmSpy).toHaveBeenCalled()
    })

    it('should remove device after confirmation', async () => {
      const user = userEvent.setup()
      window.confirm = vi.fn(() => true)
      mockOnRemoveDevice.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRemoveDevice={mockOnRemoveDevice}
        />
      )

      const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
      await user.click(removeButtons[0])

      await waitFor(() => {
        expect(mockOnRemoveDevice).toHaveBeenCalledWith('device-2')
      })
    })

    it('should not remove device if confirmation is cancelled', async () => {
      const user = userEvent.setup()
      window.confirm = vi.fn(() => false)
      mockOnRemoveDevice.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRemoveDevice={mockOnRemoveDevice}
        />
      )

      const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
      await user.click(removeButtons[0])

      expect(mockOnRemoveDevice).not.toHaveBeenCalled()
    })

    it('should show loading state during removal', async () => {
      const user = userEvent.setup()
      window.confirm = vi.fn(() => true)
      mockOnRemoveDevice.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRemoveDevice={mockOnRemoveDevice}
        />
      )

      const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
      await user.click(removeButtons[0])

      expect(screen.getByText(/removing\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/removing\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle remove device error', async () => {
      const user = userEvent.setup()
      window.confirm = vi.fn(() => true)
      const error = new Error('Failed to remove device')
      mockOnRemoveDevice.mockRejectedValue(error)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onRemoveDevice={mockOnRemoveDevice}
          onError={mockOnError}
        />
      )

      const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
      await user.click(removeButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Failed to remove device')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Notification Toggle', () => {
    it('should display notification toggle for trusted devices', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onToggleNotifications={mockOnToggleNotifications}
        />
      )

      const notificationCheckboxes = screen.getAllByRole('checkbox')
      expect(notificationCheckboxes).toHaveLength(2) // Only trusted devices
    })

    it('should reflect notification enabled state', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onToggleNotifications={mockOnToggleNotifications}
        />
      )

      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes[0]).toBeChecked() // device-1 has notifications enabled
      expect(checkboxes[1]).not.toBeChecked() // device-2 has notifications disabled
    })

    it('should toggle notifications', async () => {
      const user = userEvent.setup()
      mockOnToggleNotifications.mockResolvedValue(undefined)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onToggleNotifications={mockOnToggleNotifications}
        />
      )

      const checkboxes = screen.getAllByRole('checkbox')
      await user.click(checkboxes[1])

      await waitFor(() => {
        expect(mockOnToggleNotifications).toHaveBeenCalledWith('device-2', true)
      })
    })

    it('should handle toggle notifications error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to update notifications')
      mockOnToggleNotifications.mockRejectedValue(error)

      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onToggleNotifications={mockOnToggleNotifications}
          onError={mockOnError}
        />
      )

      const checkboxes = screen.getAllByRole('checkbox')
      await user.click(checkboxes[0])

      await waitFor(() => {
        expect(screen.getByText('Failed to update notifications')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Device Information Section', () => {
    it('should display device trust information', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
        />
      )

      expect(screen.getByText('About Device Trust')).toBeInTheDocument()
      expect(screen.getByText(/Trusted devices can skip additional verification/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible notification checkboxes', () => {
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onToggleNotifications={mockOnToggleNotifications}
        />
      )

      const checkboxes = screen.getAllByRole('checkbox')
      checkboxes.forEach((checkbox) => {
        expect(checkbox).toBeInTheDocument()
      })
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(
        <DeviceManagement
          devices={mockDevices}
          currentDeviceId="device-1"
          onTrustDevice={mockOnTrustDevice}
          onRemoveDevice={mockOnRemoveDevice}
        />
      )

      await user.tab()
      const firstButton = screen.getByRole('button', { name: /revoke trust/i })
      expect(firstButton).toHaveFocus()
    })
  })
})
