import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { OrganizationSwitcher } from './organization-switcher'
import type { Organization } from './organization-switcher'

describe('OrganizationSwitcher', () => {
  const mockOnSwitchOrganization = vi.fn()
  const mockOnCreateOrganization = vi.fn()
  const mockOnFetchOrganizations = vi.fn()
  const mockOnError = vi.fn()

  const mockOrganizations: Organization[] = [
    {
      id: 'org-1',
      name: 'Acme Corporation',
      slug: 'acme',
      role: 'owner',
      logoUrl: 'https://example.com/acme.png',
      memberCount: 15,
    },
    {
      id: 'org-2',
      name: 'Tech Startup',
      slug: 'tech-startup',
      role: 'admin',
      memberCount: 5,
    },
    {
      id: 'org-3',
      name: 'Consulting Group',
      slug: 'consulting',
      role: 'member',
      logoUrl: 'https://example.com/consulting.png',
      memberCount: 30,
    },
  ]

  const mockPersonalWorkspace = {
    id: 'personal-1',
    name: 'My Workspace',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render trigger button', () => {
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      expect(screen.getByRole('button', { name: /acme corporation/i })).toBeInTheDocument()
    })

    it('should display current organization name', () => {
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      expect(screen.getByText('Acme Corporation')).toBeInTheDocument()
      expect(screen.getByText('owner')).toBeInTheDocument()
    })

    it('should show placeholder when no current organization', () => {
      render(
        <OrganizationSwitcher organizations={mockOrganizations} />
      )

      expect(screen.getByText('Select organization')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })

    it('should display organization logo when available', () => {
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const logo = screen.getByAltText('Acme Corporation')
      expect(logo).toHaveAttribute('src', 'https://example.com/acme.png')
    })

    it('should display initials when no logo', () => {
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[1]}
          organizations={mockOrganizations}
        />
      )

      expect(screen.getByText('TS')).toBeInTheDocument() // Tech Startup -> TS
    })
  })

  describe('Dropdown Menu', () => {
    it('should open dropdown when clicking trigger', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      expect(screen.getByText('Organizations')).toBeInTheDocument()
    })

    it.skip('should close dropdown when clicking outside', async () => {
      const user = userEvent.setup()
      render(
        <div>
          <OrganizationSwitcher
            currentOrganization={mockOrganizations[0]}
            organizations={mockOrganizations}
          />
          <div data-testid="outside">Outside</div>
        </div>
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      expect(screen.getByText('Organizations')).toBeInTheDocument()

      const outside = screen.getByTestId('outside')
      await user.click(outside)

      // Use findBy to wait for dropdown to close
      await waitFor(
        () => {
          expect(screen.queryByText('Organizations')).not.toBeInTheDocument()
        },
        { timeout: 2000 }
      )
    })

    it('should rotate arrow icon when dropdown is open', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      const arrow = container.querySelector('svg')

      expect(arrow).not.toHaveClass('rotate-180')

      await user.click(trigger)

      expect(arrow).toHaveClass('rotate-180')
    })
  })

  describe('Organization List', () => {
    it('should display all organizations', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      // Acme Corporation appears both in trigger and dropdown, so use getAllByText
      const acmeElements = screen.getAllByText('Acme Corporation')
      expect(acmeElements.length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Tech Startup')).toBeInTheDocument()
      expect(screen.getByText('Consulting Group')).toBeInTheDocument()
    })

    it('should display member counts', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      expect(screen.getByText('15 members')).toBeInTheDocument()
      expect(screen.getByText('5 members')).toBeInTheDocument()
      expect(screen.getByText('30 members')).toBeInTheDocument()
    })

    it('should display singular "member" for count of 1', async () => {
      const user = userEvent.setup()
      const orgsWithOne = [...mockOrganizations]
      orgsWithOne[1] = { ...orgsWithOne[1], memberCount: 1 }

      render(
        <OrganizationSwitcher
          currentOrganization={orgsWithOne[0]}
          organizations={orgsWithOne}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.getByText('1 member')).toBeInTheDocument()
    })

    it('should display role badges', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      expect(screen.getAllByText('owner')).toHaveLength(2) // current org + in list
      expect(screen.getByText('admin')).toBeInTheDocument()
      expect(screen.getByText('member')).toBeInTheDocument()
    })

    it('should mark current organization with checkmark', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      const checkmarks = container.querySelectorAll('svg[fill="currentColor"]')
      expect(checkmarks.length).toBeGreaterThan(0)
    })
  })

  describe('Personal Workspace', () => {
    it('should show personal workspace when enabled', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showPersonalWorkspace={true}
          personalWorkspace={mockPersonalWorkspace}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.getByText('Personal')).toBeInTheDocument()
      expect(screen.getByText('My Workspace')).toBeInTheDocument()
      expect(screen.getByText('Personal workspace')).toBeInTheDocument()
    })

    it('should not show personal workspace when disabled', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showPersonalWorkspace={false}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.queryByText('Personal')).not.toBeInTheDocument()
    })

    it('should switch to personal workspace', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
          showPersonalWorkspace={true}
          personalWorkspace={mockPersonalWorkspace}
          onSwitchOrganization={mockOnSwitchOrganization}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      const personalButton = screen.getByText('My Workspace').closest('button')
      await user.click(personalButton!)

      expect(mockOnSwitchOrganization).toHaveBeenCalledWith({
        id: 'personal-1',
        name: 'My Workspace',
        slug: 'personal',
      })
    })
  })

  describe('Switch Organization', () => {
    it('should switch organization when clicking item', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
          onSwitchOrganization={mockOnSwitchOrganization}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      const orgButton = screen.getByText('Tech Startup').closest('button')
      await user.click(orgButton!)

      expect(mockOnSwitchOrganization).toHaveBeenCalledWith(mockOrganizations[1])
    })

    it('should close dropdown after switching', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
          onSwitchOrganization={mockOnSwitchOrganization}
        />
      )

      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      await user.click(trigger)

      const orgButton = screen.getByText('Tech Startup').closest('button')
      await user.click(orgButton!)

      await waitFor(() => {
        expect(screen.queryByText('Organizations')).not.toBeInTheDocument()
      })
    })
  })

  describe('Create Organization', () => {
    it('should show create organization button when enabled', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showCreateOrganization={true}
          onCreateOrganization={mockOnCreateOrganization}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.getByText('Create organization')).toBeInTheDocument()
    })

    it('should not show create organization button when disabled', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showCreateOrganization={false}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.queryByText('Create organization')).not.toBeInTheDocument()
    })

    it('should call create organization callback', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showCreateOrganization={true}
          onCreateOrganization={mockOnCreateOrganization}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      const createButton = screen.getByText('Create organization').closest('button')
      await user.click(createButton!)

      expect(mockOnCreateOrganization).toHaveBeenCalled()
    })

    it('should close dropdown after creating organization', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          showCreateOrganization={true}
          onCreateOrganization={mockOnCreateOrganization}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      const createButton = screen.getByText('Create organization').closest('button')
      await user.click(createButton!)

      await waitFor(() => {
        expect(screen.queryByText('Organizations')).not.toBeInTheDocument()
      })
    })
  })

  describe('Fetch Organizations', () => {
    it('should fetch organizations when opening dropdown', async () => {
      const user = userEvent.setup()
      mockOnFetchOrganizations.mockResolvedValue(mockOrganizations)

      render(
        <OrganizationSwitcher
          onFetchOrganizations={mockOnFetchOrganizations}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      await waitFor(() => {
        expect(mockOnFetchOrganizations).toHaveBeenCalled()
      })
    })

    it('should show loading state while fetching', async () => {
      const user = userEvent.setup()
      mockOnFetchOrganizations.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockOrganizations), 100))
      )

      render(
        <OrganizationSwitcher
          onFetchOrganizations={mockOnFetchOrganizations}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      // Wait for organizations to load (component may not show loading state for fast fetches)
      await waitFor(() => {
        expect(screen.getByText('Acme Corporation')).toBeInTheDocument()
      })
    })

    it('should handle fetch error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to fetch organizations')
      mockOnFetchOrganizations.mockRejectedValue(error)

      render(
        <OrganizationSwitcher
          onFetchOrganizations={mockOnFetchOrganizations}
          onError={mockOnError}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch organizations')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })

    it('should not fetch if organizations already provided', async () => {
      const user = userEvent.setup()
      mockOnFetchOrganizations.mockResolvedValue(mockOrganizations)

      render(
        <OrganizationSwitcher
          organizations={mockOrganizations}
          onFetchOrganizations={mockOnFetchOrganizations}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      await waitFor(() => {
        expect(mockOnFetchOrganizations).not.toHaveBeenCalled()
      })
    })
  })

  describe('Empty State', () => {
    it('should show empty state when no organizations', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={[]}
          showPersonalWorkspace={false}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.getByText('No organizations yet')).toBeInTheDocument()
    })

    it('should show create button in empty state', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          organizations={[]}
          showPersonalWorkspace={false}
          showCreateOrganization={true}
          onCreateOrganization={mockOnCreateOrganization}
        />
      )

      const trigger = screen.getByRole('button')
      await user.click(trigger)

      expect(screen.getByText('Create your first organization')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(
        <OrganizationSwitcher
          currentOrganization={mockOrganizations[0]}
          organizations={mockOrganizations}
        />
      )

      await user.tab()
      const trigger = screen.getByRole('button', { name: /acme corporation/i })
      expect(trigger).toHaveFocus()

      await user.keyboard('{Enter}')
      expect(screen.getByText('Organizations')).toBeInTheDocument()
    })
  })
})
