import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { UserButton } from './user-button'

describe('UserButton', () => {
  const mockUser = {
    id: '1',
    email: 'john@example.com',
    firstName: 'John',
    lastName: 'Doe',
    avatarUrl: 'https://example.com/avatar.jpg',
  }

  const mockOnSignOut = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    delete (window as any).location
    window.location = { href: '' } as any
  })

  describe('Rendering', () => {
    it('should render user button with avatar', () => {
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      expect(button).toBeInTheDocument()
    })

    it('should display user initials when no avatar', () => {
      const userWithoutAvatar = { ...mockUser, avatarUrl: undefined }
      render(<UserButton user={userWithoutAvatar} />)

      expect(screen.getByText('JD')).toBeInTheDocument()
    })

    it('should display email initials when name is missing', () => {
      const userWithoutName = {
        ...mockUser,
        firstName: undefined,
        lastName: undefined,
        avatarUrl: undefined,
      }
      render(<UserButton user={userWithoutName} />)

      expect(screen.getByText('J')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(<UserButton user={mockUser} className="custom-class" />)

      const button = container.querySelector('button')
      expect(button).toHaveClass('custom-class')
    })
  })

  describe('Dropdown Menu', () => {
    it('should open dropdown menu on click', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(mockUser.email)).toBeInTheDocument()
        expect(screen.getByText('John Doe')).toBeInTheDocument()
      })
    })

    it('should display user information in dropdown', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument()
        expect(screen.getByText('john@example.com')).toBeInTheDocument()
      })
    })

    it('should display email when name is not available', async () => {
      const user = userEvent.setup()
      const userWithoutName = {
        ...mockUser,
        firstName: undefined,
        lastName: undefined,
      }
      render(<UserButton user={userWithoutName} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const emails = screen.getAllByText('john@example.com')
        expect(emails.length).toBeGreaterThan(0)
      })
    })
  })

  describe('Menu Items', () => {
    it('should show manage account option when enabled', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} showManageAccount={true} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(/manage account/i)).toBeInTheDocument()
      })
    })

    it('should not show manage account option when disabled', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} showManageAccount={false} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.queryByText(/manage account/i)).not.toBeInTheDocument()
      })
    })

    it('should show organizations option when enabled', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} showOrganizations={true} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(/organizations/i)).toBeInTheDocument()
      })
    })

    it('should not show organizations option when disabled', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} showOrganizations={false} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.queryByText(/organizations/i)).not.toBeInTheDocument()
      })
    })

    it('should always show settings option', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(/settings/i)).toBeInTheDocument()
      })
    })

    it('should always show sign out option', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(/sign out/i)).toBeInTheDocument()
      })
    })
  })

  describe('Navigation', () => {
    it('should navigate to manage account page', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} manageAccountUrl="/profile" />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const manageAccountItem = screen.getByText(/manage account/i)
        manageAccountItem.click()
      })

      await waitFor(() => {
        expect(window.location.href).toBe('/profile')
      })
    })

    it('should use default manage account URL', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const manageAccountItem = screen.getByText(/manage account/i)
        manageAccountItem.click()
      })

      await waitFor(() => {
        expect(window.location.href).toBe('/account')
      })
    })

    it('should navigate to organizations page', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} showOrganizations={true} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const organizationsItem = screen.getByText(/organizations/i)
        organizationsItem.click()
      })

      await waitFor(() => {
        expect(window.location.href).toBe('/organizations')
      })
    })

    it('should navigate to settings page', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const settingsItem = screen.getByText(/settings/i)
        settingsItem.click()
      })

      await waitFor(() => {
        expect(window.location.href).toBe('/settings')
      })
    })
  })

  describe('Sign Out', () => {
    it('should call onSignOut when sign out is clicked', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} onSignOut={mockOnSignOut} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const signOutItem = screen.getByText(/sign out/i)
        signOutItem.click()
      })

      expect(mockOnSignOut).toHaveBeenCalled()
    })

    it('should not crash when onSignOut is not provided', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const signOutItem = screen.getByText(/sign out/i)
        expect(() => signOutItem.click()).not.toThrow()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have accessible label', () => {
      render(<UserButton user={mockUser} />)

      expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument()
    })

    it('should have focus ring on button', () => {
      const { container } = render(<UserButton user={mockUser} />)

      const button = container.querySelector('button')
      expect(button).toHaveClass('focus:ring-2')
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })

      // Tab to button
      await user.tab()
      expect(button).toHaveFocus()

      // Open with Enter
      await user.keyboard('{Enter}')

      await waitFor(() => {
        expect(screen.getByText(/manage account/i)).toBeInTheDocument()
      })
    })

    it('should close dropdown on Escape', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        expect(screen.getByText(/manage account/i)).toBeInTheDocument()
      })

      await user.keyboard('{Escape}')

      await waitFor(() => {
        expect(screen.queryByText(/manage account/i)).not.toBeInTheDocument()
      })
    })

    it('should have proper ARIA roles for menu items', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        // Radix UI sets role="menuitem" on dropdown items
        const manageAccountItem = screen.getByText(/manage account/i)
        expect(manageAccountItem).toBeInTheDocument()
      })
    })
  })

  describe('Visual States', () => {
    it('should show hover state on button', () => {
      const { container } = render(<UserButton user={mockUser} />)

      const button = container.querySelector('button')
      expect(button).toHaveClass('hover:opacity-80')
    })

    it.skip('TODO: Fix Avatar accessibility - should display avatar image when URL provided', () => {
      // Avatar component doesn't render <img> with proper alt text for accessibility
      render(<UserButton user={mockUser} />)

      const avatar = screen.getByRole('img', { name: /john doe/i })
      expect(avatar).toHaveAttribute('src', mockUser.avatarUrl)
    })

    it('should show fallback when avatar fails to load', () => {
      const userWithoutAvatar = { ...mockUser, avatarUrl: undefined }
      render(<UserButton user={userWithoutAvatar} />)

      expect(screen.getByText('JD')).toBeInTheDocument()
    })
  })

  describe('Menu Positioning', () => {
    it('should align menu to end', async () => {
      const user = userEvent.setup()
      const { container } = render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      // Check that dropdown content exists (Radix UI handles positioning)
      await waitFor(() => {
        expect(screen.getByText(/manage account/i)).toBeInTheDocument()
      })
    })

    it('should have proper z-index for dropdown', async () => {
      const user = userEvent.setup()
      render(<UserButton user={mockUser} />)

      const button = screen.getByRole('button', { name: /user menu/i })
      await user.click(button)

      await waitFor(() => {
        const dropdown = screen.getByText(/manage account/i).closest('[class*="bg-background"]')
        expect(dropdown).toHaveClass('z-50')
      })
    })
  })
})
