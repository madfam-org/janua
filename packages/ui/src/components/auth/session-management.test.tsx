import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { SessionManagement } from './session-management'
import type { Session } from './session-management'

describe('SessionManagement', () => {
  const mockOnRevokeSession = vi.fn()
  const mockOnRevokeAllOthers = vi.fn()
  const mockOnError = vi.fn()

  const mockSessions: Session[] = [
    {
      id: 'session-1',
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
      createdAt: new Date('2024-01-01'),
      lastActiveAt: new Date(Date.now() - 300000), // 5 minutes ago
      isCurrent: true,
    },
    {
      id: 'session-2',
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
      createdAt: new Date('2024-01-02'),
      lastActiveAt: new Date(Date.now() - 3600000), // 1 hour ago
      warnings: ['unusual_location'],
    },
    {
      id: 'session-3',
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
      createdAt: new Date('2024-01-03'),
      lastActiveAt: new Date(Date.now() - 86400000), // 1 day ago
      warnings: ['new_device', 'suspicious_activity'],
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render session management component', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText('Active Sessions')).toBeInTheDocument()
      expect(screen.getByText(/Manage your active sessions/i)).toBeInTheDocument()
    })

    it('should render all sessions', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText('Chrome on Windows')).toBeInTheDocument()
      expect(screen.getByText('Safari on iPhone')).toBeInTheDocument()
      expect(screen.getByText('iPad')).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          logoUrl="https://example.com/logo.png"
        />
      )

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })

    it('should display empty state when no sessions', () => {
      render(
        <SessionManagement sessions={[]} currentSessionId="current" />
      )

      expect(screen.getByText('No active sessions found')).toBeInTheDocument()
    })
  })

  describe('Session Display', () => {
    it('should mark current session with badge', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText('Current Session')).toBeInTheDocument()
    })

    it('should display device information', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/Chrome on Windows 10/i)).toBeInTheDocument()
      expect(screen.getByText(/Safari on iOS 17/i)).toBeInTheDocument()
    })

    it('should display location information', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/New York, USA/i)).toBeInTheDocument()
      expect(screen.getByText(/San Francisco, USA/i)).toBeInTheDocument()
    })

    it('should display relative timestamps', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/Last active 5m ago/i)).toBeInTheDocument()
      expect(screen.getByText(/Last active 1h ago/i)).toBeInTheDocument()
      expect(screen.getByText(/Last active 1d ago/i)).toBeInTheDocument()
    })

    it('should render device type icons', () => {
      const { container } = render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      const icons = container.querySelectorAll('svg')
      expect(icons.length).toBeGreaterThan(0)
    })
  })

  describe('Security Warnings', () => {
    it('should display unusual location warning', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/Unusual location/i)).toBeInTheDocument()
    })

    it('should display new device warning', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/New device/i)).toBeInTheDocument()
    })

    it('should display suspicious activity warning', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/Suspicious activity/i)).toBeInTheDocument()
    })

    it('should apply warning styling to sessions with warnings', () => {
      const { container } = render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      const sessionElements = container.querySelectorAll('.border-yellow-500')
      expect(sessionElements.length).toBe(2) // session-2 and session-3 have warnings
    })
  })

  describe('Revoke Session', () => {
    it('should revoke individual session', async () => {
      const user = userEvent.setup()
      mockOnRevokeSession.mockResolvedValue(undefined)

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      await user.click(revokeButtons[0])

      await waitFor(() => {
        expect(mockOnRevokeSession).toHaveBeenCalledWith('session-2')
      })
    })

    it('should not show revoke button for current session', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      // Should only have 2 revoke buttons (for session-2 and session-3, not session-1)
      expect(revokeButtons.length).toBe(2)
    })

    it('should show loading state during revoke', async () => {
      const user = userEvent.setup()
      mockOnRevokeSession.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      await user.click(revokeButtons[0])

      expect(screen.getByText(/revoking\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/revoking\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle revoke error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to revoke session')
      mockOnRevokeSession.mockRejectedValue(error)

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
          onError={mockOnError}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      await user.click(revokeButtons[0])

      await waitFor(() => {
        expect(screen.getByText('Failed to revoke session')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })

    it('should disable button during revoke', async () => {
      const user = userEvent.setup()
      mockOnRevokeSession.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      await user.click(revokeButtons[0])

      expect(revokeButtons[0]).toBeDisabled()
    })
  })

  describe('Revoke All Others', () => {
    it('should show revoke all button when other sessions exist', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeAllOthers={mockOnRevokeAllOthers}
        />
      )

      expect(screen.getByRole('button', { name: /revoke all other sessions/i })).toBeInTheDocument()
    })

    it('should not show revoke all button when no other sessions', () => {
      render(
        <SessionManagement
          sessions={[mockSessions[0]]}
          currentSessionId="session-1"
          onRevokeAllOthers={mockOnRevokeAllOthers}
        />
      )

      expect(screen.queryByRole('button', { name: /revoke all other sessions/i })).not.toBeInTheDocument()
    })

    it('should revoke all other sessions', async () => {
      const user = userEvent.setup()
      mockOnRevokeAllOthers.mockResolvedValue(undefined)

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeAllOthers={mockOnRevokeAllOthers}
        />
      )

      const revokeAllButton = screen.getByRole('button', { name: /revoke all other sessions/i })
      await user.click(revokeAllButton)

      await waitFor(() => {
        expect(mockOnRevokeAllOthers).toHaveBeenCalled()
      })
    })

    it('should show loading state during revoke all', async () => {
      const user = userEvent.setup()
      mockOnRevokeAllOthers.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeAllOthers={mockOnRevokeAllOthers}
        />
      )

      const revokeAllButton = screen.getByRole('button', { name: /revoke all other sessions/i })
      await user.click(revokeAllButton)

      expect(screen.getByText(/revoking\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/revoking\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle revoke all error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to revoke sessions')
      mockOnRevokeAllOthers.mockRejectedValue(error)

      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeAllOthers={mockOnRevokeAllOthers}
          onError={mockOnError}
        />
      )

      const revokeAllButton = screen.getByRole('button', { name: /revoke all other sessions/i })
      await user.click(revokeAllButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to revoke sessions')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Security Information', () => {
    it('should display security tips', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
        />
      )

      expect(screen.getByText(/Security Tips/i)).toBeInTheDocument()
      expect(screen.getByText(/If you see a session you don't recognize/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible revoke buttons', () => {
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
        />
      )

      const revokeButtons = screen.getAllByRole('button', { name: /revoke/i })
      revokeButtons.forEach((button) => {
        expect(button).toBeInTheDocument()
      })
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(
        <SessionManagement
          sessions={mockSessions}
          currentSessionId="session-1"
          onRevokeSession={mockOnRevokeSession}
          onRevokeAllOthers={mockOnRevokeAllOthers}
        />
      )

      await user.tab()
      const revokeAllButton = screen.getByRole('button', { name: /revoke all other sessions/i })
      expect(revokeAllButton).toHaveFocus()

      await user.tab()
      const firstRevokeButton = screen.getAllByRole('button', { name: /^revoke$/i })[0]
      expect(firstRevokeButton).toHaveFocus()
    })
  })
})
