import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { AuditLog } from './audit-log'
import type { AuditEvent } from './audit-log'

describe('AuditLog', () => {
  const mockOnLoadMore = vi.fn()
  const mockOnExport = vi.fn()
  const mockOnError = vi.fn()

  const mockEvents: AuditEvent[] = [
    {
      id: 'event-1',
      type: 'auth.login',
      category: 'auth',
      actor: {
        id: 'user-1',
        email: 'john@example.com',
        name: 'John Doe',
      },
      ipAddress: '192.168.1.1',
      location: {
        city: 'New York',
        country: 'USA',
      },
      timestamp: new Date(Date.now() - 300000), // 5 minutes ago
      severity: 'info',
    },
    {
      id: 'event-2',
      type: 'security.session_revoked',
      category: 'security',
      actor: {
        id: 'user-1',
        email: 'john@example.com',
        name: 'John Doe',
      },
      target: {
        id: 'session-123',
        type: 'session',
      },
      ipAddress: '192.168.1.2',
      location: {
        city: 'San Francisco',
        country: 'USA',
      },
      timestamp: new Date(Date.now() - 3600000), // 1 hour ago
      severity: 'warning',
      metadata: {
        reason: 'suspicious_activity',
        sessionDuration: '2h 30m',
      },
    },
    {
      id: 'event-3',
      type: 'security.suspicious_activity',
      category: 'security',
      actor: {
        id: 'user-2',
        email: 'jane@example.com',
      },
      ipAddress: '10.0.0.1',
      location: {
        city: 'London',
        country: 'UK',
      },
      timestamp: new Date(Date.now() - 86400000), // 1 day ago
      severity: 'critical',
    },
    {
      id: 'event-4',
      type: 'admin.user_created',
      category: 'admin',
      actor: {
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin User',
      },
      target: {
        id: 'user-3',
        email: 'newuser@example.com',
        name: 'New User',
      },
      ipAddress: '172.16.0.1',
      timestamp: new Date(Date.now() - 172800000), // 2 days ago
      severity: 'info',
    },
    {
      id: 'event-5',
      type: 'compliance.data_export',
      category: 'compliance',
      actor: {
        id: 'user-1',
        email: 'john@example.com',
        name: 'John Doe',
      },
      ipAddress: '192.168.1.1',
      timestamp: new Date(Date.now() - 604800000), // 7 days ago
      severity: 'info',
      metadata: {
        format: 'json',
        recordCount: 150,
      },
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render audit log component', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('Audit Log')).toBeInTheDocument()
      expect(screen.getByText(/Security events and user activity/i)).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(<AuditLog events={mockEvents} logoUrl="https://example.com/logo.png" />)

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(<AuditLog events={mockEvents} className="custom-class" />)

      expect(container.firstChild).toHaveClass('custom-class')
    })

    it('should render all events', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('Login')).toBeInTheDocument()
      expect(screen.getByText('Session Revoked')).toBeInTheDocument()
      expect(screen.getByText('Suspicious Activity')).toBeInTheDocument()
      expect(screen.getByText('User Created')).toBeInTheDocument()
      expect(screen.getByText('Data Export')).toBeInTheDocument()
    })
  })

  describe('Event Display', () => {
    it('should display event actors', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.getByText('jane@example.com')).toBeInTheDocument()
      expect(screen.getByText('Admin User')).toBeInTheDocument()
    })

    it('should display event targets', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('New User')).toBeInTheDocument()
    })

    it('should display IP addresses', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText(/IP: 192\.168\.1\.1/i)).toBeInTheDocument()
      expect(screen.getByText(/IP: 192\.168\.1\.2/i)).toBeInTheDocument()
      expect(screen.getByText(/IP: 10\.0\.0\.1/i)).toBeInTheDocument()
    })

    it('should display locations', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText(/New York, USA/i)).toBeInTheDocument()
      expect(screen.getByText(/San Francisco, USA/i)).toBeInTheDocument()
      expect(screen.getByText(/London, UK/i)).toBeInTheDocument()
    })

    it('should display relative timestamps', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText(/5m ago/i)).toBeInTheDocument()
      expect(screen.getByText(/1h ago/i)).toBeInTheDocument()
      expect(screen.getByText(/1d ago/i)).toBeInTheDocument()
    })

    it('should display severity badges', () => {
      render(<AuditLog events={mockEvents} />)

      const criticalBadge = screen.getByText('critical')
      const warningBadge = screen.getByText('warning')
      const infoBadges = screen.getAllByText('info')

      expect(criticalBadge).toBeInTheDocument()
      expect(warningBadge).toBeInTheDocument()
      expect(infoBadges.length).toBeGreaterThan(0)
    })

    it('should display category labels', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('auth')).toBeInTheDocument()
      expect(screen.getAllByText('security')).toHaveLength(2)
      expect(screen.getByText('admin')).toBeInTheDocument()
      expect(screen.getByText('compliance')).toBeInTheDocument()
    })

    it('should display metadata when available', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} />)

      const metadataButtons = screen.getAllByText('View metadata')
      await user.click(metadataButtons[0])

      expect(screen.getByText(/"reason": "suspicious_activity"/i)).toBeInTheDocument()
    })
  })

  describe('Filters', () => {
    it('should show filters when enabled', () => {
      render(<AuditLog events={mockEvents} showFilters={true} />)

      expect(screen.getByLabelText(/search/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/category/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/severity/i)).toBeInTheDocument()
    })

    it('should not show filters when disabled', () => {
      render(<AuditLog events={mockEvents} showFilters={false} />)

      expect(screen.queryByLabelText(/search/i)).not.toBeInTheDocument()
    })

    it('should filter by search term', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showFilters={true} />)

      const searchInput = screen.getByLabelText(/search/i)
      await user.type(searchInput, 'john@example.com')

      // Should show events by john@example.com (3 events)
      expect(screen.getByText('Login')).toBeInTheDocument()
      expect(screen.getByText('Session Revoked')).toBeInTheDocument()
      expect(screen.getByText('Data Export')).toBeInTheDocument()

      // Should not show events by other users
      expect(screen.queryByText('Suspicious Activity')).not.toBeInTheDocument()
      expect(screen.queryByText('User Created')).not.toBeInTheDocument()
    })

    it('should filter by category', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showFilters={true} />)

      const categorySelect = screen.getByLabelText(/category/i)
      await user.selectOptions(categorySelect, 'security')

      // Should show only security events
      expect(screen.getByText('Session Revoked')).toBeInTheDocument()
      expect(screen.getByText('Suspicious Activity')).toBeInTheDocument()

      // Should not show other category events
      expect(screen.queryByText('Login')).not.toBeInTheDocument()
      expect(screen.queryByText('User Created')).not.toBeInTheDocument()
      expect(screen.queryByText('Data Export')).not.toBeInTheDocument()
    })

    it('should filter by severity', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showFilters={true} />)

      const severitySelect = screen.getByLabelText(/severity/i)
      await user.selectOptions(severitySelect, 'critical')

      // Should show only critical events
      expect(screen.getByText('Suspicious Activity')).toBeInTheDocument()

      // Should not show other severity events
      expect(screen.queryByText('Login')).not.toBeInTheDocument()
      expect(screen.queryByText('Session Revoked')).not.toBeInTheDocument()
    })

    it('should combine multiple filters', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showFilters={true} />)

      const searchInput = screen.getByLabelText(/search/i)
      const categorySelect = screen.getByLabelText(/category/i)

      await user.type(searchInput, 'john')
      await user.selectOptions(categorySelect, 'auth')

      // Should show only auth events by john
      expect(screen.getByText('Login')).toBeInTheDocument()

      // Should not show security events even though they're by john
      expect(screen.queryByText('Session Revoked')).not.toBeInTheDocument()
    })

    it('should show no results message when filters match nothing', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showFilters={true} />)

      const searchInput = screen.getByLabelText(/search/i)
      await user.type(searchInput, 'nonexistent@example.com')

      expect(screen.getByText('No audit events found')).toBeInTheDocument()
      expect(screen.getByText(/Try adjusting your filters/i)).toBeInTheDocument()
    })
  })

  describe('Export Functionality', () => {
    it('should show export buttons when enabled', () => {
      render(<AuditLog events={mockEvents} showExport={true} onExport={mockOnExport} />)

      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /export json/i })).toBeInTheDocument()
    })

    it('should not show export buttons when disabled', () => {
      render(<AuditLog events={mockEvents} showExport={false} />)

      expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /export json/i })).not.toBeInTheDocument()
    })

    it('should export as CSV', async () => {
      const user = userEvent.setup()
      mockOnExport.mockResolvedValue(undefined)

      render(<AuditLog events={mockEvents} showExport={true} onExport={mockOnExport} />)

      const csvButton = screen.getByRole('button', { name: /export csv/i })
      await user.click(csvButton)

      await waitFor(() => {
        expect(mockOnExport).toHaveBeenCalledWith('csv', expect.any(Object))
      })
    })

    it('should export as JSON', async () => {
      const user = userEvent.setup()
      mockOnExport.mockResolvedValue(undefined)

      render(<AuditLog events={mockEvents} showExport={true} onExport={mockOnExport} />)

      const jsonButton = screen.getByRole('button', { name: /export json/i })
      await user.click(jsonButton)

      await waitFor(() => {
        expect(mockOnExport).toHaveBeenCalledWith('json', expect.any(Object))
      })
    })

    it('should show loading state during export', async () => {
      const user = userEvent.setup()
      mockOnExport.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<AuditLog events={mockEvents} showExport={true} onExport={mockOnExport} />)

      const csvButton = screen.getByRole('button', { name: /export csv/i })
      await user.click(csvButton)

      expect(screen.getByText(/exporting\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/exporting\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle export error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to export as CSV')
      mockOnExport.mockRejectedValue(error)

      render(<AuditLog events={mockEvents} showExport={true} onExport={mockOnExport} onError={mockOnError} />)

      const csvButton = screen.getByRole('button', { name: /export csv/i })
      await user.click(csvButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to export as CSV')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })

    it('should pass current filters to export', async () => {
      const user = userEvent.setup()
      mockOnExport.mockResolvedValue(undefined)

      render(<AuditLog events={mockEvents} showExport={true} showFilters={true} onExport={mockOnExport} />)

      const categorySelect = screen.getByLabelText(/category/i)
      await user.selectOptions(categorySelect, 'security')

      const csvButton = screen.getByRole('button', { name: /export csv/i })
      await user.click(csvButton)

      await waitFor(() => {
        expect(mockOnExport).toHaveBeenCalledWith('csv', expect.objectContaining({
          category: 'security',
        }))
      })
    })
  })

  describe('Load More', () => {
    it('should show load more button when hasMore is true', () => {
      render(<AuditLog events={mockEvents} hasMore={true} onLoadMore={mockOnLoadMore} />)

      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument()
    })

    it('should not show load more button when hasMore is false', () => {
      render(<AuditLog events={mockEvents} hasMore={false} onLoadMore={mockOnLoadMore} />)

      expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument()
    })

    it('should load more events', async () => {
      const user = userEvent.setup()
      mockOnLoadMore.mockResolvedValue(undefined)

      render(<AuditLog events={mockEvents} hasMore={true} onLoadMore={mockOnLoadMore} />)

      const loadMoreButton = screen.getByRole('button', { name: /load more/i })
      await user.click(loadMoreButton)

      await waitFor(() => {
        expect(mockOnLoadMore).toHaveBeenCalled()
      })
    })

    it('should show loading state during load more', async () => {
      const user = userEvent.setup()
      mockOnLoadMore.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<AuditLog events={mockEvents} hasMore={true} onLoadMore={mockOnLoadMore} />)

      const loadMoreButton = screen.getByRole('button', { name: /load more/i })
      await user.click(loadMoreButton)

      expect(screen.getByText(/loading\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/loading\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle load more error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to load more events')
      mockOnLoadMore.mockRejectedValue(error)

      render(<AuditLog events={mockEvents} hasMore={true} onLoadMore={mockOnLoadMore} onError={mockOnError} />)

      const loadMoreButton = screen.getByRole('button', { name: /load more/i })
      await user.click(loadMoreButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to load more events')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })

    it('should display event count in load more button', () => {
      render(<AuditLog events={mockEvents} hasMore={true} onLoadMore={mockOnLoadMore} />)

      expect(screen.getByText(/Load more events \(5 shown\)/i)).toBeInTheDocument()
    })
  })

  describe('Empty State', () => {
    it('should display empty state when no events', () => {
      render(<AuditLog events={[]} />)

      expect(screen.getByText('No audit events found')).toBeInTheDocument()
    })

    it('should not show compliance info in empty state', () => {
      render(<AuditLog events={[]} />)

      expect(screen.getByText('Compliance & Audit Trail')).toBeInTheDocument()
    })
  })

  describe('Compliance Information', () => {
    it('should display compliance information', () => {
      render(<AuditLog events={mockEvents} />)

      expect(screen.getByText('Compliance & Audit Trail')).toBeInTheDocument()
      expect(screen.getByText(/All security events are logged/i)).toBeInTheDocument()
      expect(screen.getByText(/GDPR, SOC 2, or HIPAA/i)).toBeInTheDocument()
    })
  })

  describe('Event Icons', () => {
    it('should display category-specific icons', () => {
      const { container } = render(<AuditLog events={mockEvents} />)

      const icons = container.querySelectorAll('svg')
      expect(icons.length).toBeGreaterThan(0)
    })

    it('should apply severity colors to icons', () => {
      const { container } = render(<AuditLog events={mockEvents} />)

      const criticalIcon = container.querySelector('.text-red-600')
      const warningIcon = container.querySelector('.text-yellow-600')

      expect(criticalIcon).toBeInTheDocument()
      expect(warningIcon).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible filter labels', () => {
      render(<AuditLog events={mockEvents} showFilters={true} />)

      expect(screen.getByLabelText(/search/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/category/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/severity/i)).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<AuditLog events={mockEvents} showExport={true} showFilters={true} onExport={mockOnExport} />)

      await user.tab()
      const exportCsvButton = screen.getByRole('button', { name: /export csv/i })
      expect(exportCsvButton).toHaveFocus()

      await user.tab()
      const exportJsonButton = screen.getByRole('button', { name: /export json/i })
      expect(exportJsonButton).toHaveFocus()
    })
  })
})
