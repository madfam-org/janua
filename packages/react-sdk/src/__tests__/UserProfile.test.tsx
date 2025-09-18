import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UserProfile } from '../components/UserProfile'
import { PlintoProvider } from '../provider'
import { PlintoClient } from '@plinto/typescript-sdk'

// Mock the Plinto SDK
const mockUpdateUser = jest.fn()
const mockGetCurrentUser = jest.fn()
const mockSignOut = jest.fn()
const mockSignIn = jest.fn()

jest.mock('@plinto/typescript-sdk', () => ({
  PlintoClient: jest.fn().mockImplementation(() => ({
    updateUser: mockUpdateUser,
    getCurrentUser: mockGetCurrentUser,
    signOut: mockSignOut,
    signIn: mockSignIn,
  })),
}))

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

const mockConfig = {
  apiKey: 'test-key',
  tenantId: 'test-tenant',
  baseUrl: 'https://api.plinto.dev'
}

const mockUser = {
  sub: 'user123',
  email: 'john.doe@example.com',
  given_name: 'John',
  family_name: 'Doe',
  name: 'John Doe',
  nickname: 'johndoe',
  picture: 'https://example.com/avatar.jpg',
  updated_at: '2023-01-01T00:00:00.000Z',
  organization_id: 'org123',
  organization_name: 'Acme Corp',
  organization_role: 'admin',
}

const mockSession = {
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
  token_type: 'Bearer',
  expires_in: 3600,
}

describe('UserProfile Component', () => {
  let mockClient: any

  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
    mockClient = new PlintoClient(mockConfig)
    ;(PlintoClient as any).mockImplementation(() => mockClient)
  })

  const renderUserProfile = (props = {}) => {
    return render(
      React.createElement(PlintoProvider, { config: mockConfig },
        React.createElement(UserProfile, props)
      )
    )
  }

  const createMockPlintoContext = (overrides = {}) => {
    return {
      user: mockUser,
      session: mockSession,
      loading: false,
      client: mockClient,
      signOut: jest.fn(),
      ...overrides
    }
  }

  describe('Rendering', () => {
    it('should render user profile information', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.getByText('john.doe@example.com')).toBeInTheDocument()
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      expect(screen.getByText('admin')).toBeInTheDocument()
    })

    it('should render loading state', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext({ loading: true, user: null })
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText(/loading/i)).toBeInTheDocument()
    })

    it('should render no user state', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext({ user: null, loading: false })
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText(/no user data/i)).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      const { container } = render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile, { className: 'custom-profile-class' })
        )
      )

      expect(container.querySelector('.custom-profile-class')).toBeInTheDocument()
    })
  })

  describe('Edit Mode', () => {
    it('should enter edit mode when edit button is clicked', async () => {
      const user = userEvent.setup()
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/last name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    })

    it('should populate edit form with current user data', async () => {
      const user = userEvent.setup()
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      expect((screen.getByLabelText(/first name/i) as HTMLInputElement).value).toBe('John')
      expect((screen.getByLabelText(/last name/i) as HTMLInputElement).value).toBe('Doe')
      expect((screen.getByLabelText(/email/i) as HTMLInputElement).value).toBe('john.doe@example.com')
    })

    it('should exit edit mode when cancel button is clicked', async () => {
      const user = userEvent.setup()
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument()
      expect(screen.queryByLabelText(/first name/i)).not.toBeInTheDocument()
    })
  })

  describe('Form Input Handling', () => {
    it('should update form data when inputs change', async () => {
      const user = userEvent.setup()
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)

      await user.clear(firstNameInput)
      await user.type(firstNameInput, 'Jane')
      await user.clear(lastNameInput)
      await user.type(lastNameInput, 'Smith')
      await user.clear(emailInput)
      await user.type(emailInput, 'jane.smith@example.com')

      expect((firstNameInput as HTMLInputElement).value).toBe('Jane')
      expect((lastNameInput as HTMLInputElement).value).toBe('Smith')
      expect((emailInput as HTMLInputElement).value).toBe('jane.smith@example.com')
    })
  })

  describe('Save Operations', () => {
    it('should successfully save profile changes', async () => {
      const user = userEvent.setup()
      const onSuccess = jest.fn()
      
      mockUpdateUser.mockResolvedValueOnce({
        sub: 'user123',
        email: 'jane.smith@example.com',
        given_name: 'Jane',
        family_name: 'Smith',
        name: 'Jane Smith',
      })

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile, { onSuccess })
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)

      await user.clear(firstNameInput)
      await user.type(firstNameInput, 'Jane')
      await user.clear(lastNameInput)
      await user.type(lastNameInput, 'Smith')
      await user.clear(emailInput)
      await user.type(emailInput, 'jane.smith@example.com')

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          given_name: 'Jane',
          family_name: 'Smith',
          email: 'jane.smith@example.com',
        })
      })

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })

      expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument()
    })

    it('should handle partial updates when some fields are empty', async () => {
      const user = userEvent.setup()
      
      mockUpdateUser.mockResolvedValueOnce({
        sub: 'user123',
        email: 'john.doe@example.com',
        given_name: 'Jonathan',
        family_name: 'Doe',
        name: 'Jonathan Doe',
      })

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const firstNameInput = screen.getByLabelText(/first name/i)
      await user.clear(firstNameInput)
      await user.type(firstNameInput, 'Jonathan')

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          given_name: 'Jonathan',
          family_name: 'Doe',
          email: 'john.doe@example.com',
        })
      })
    })

    it('should require email field validation', async () => {
      const user = userEvent.setup()

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const emailInput = screen.getByLabelText(/email/i)
      await user.clear(emailInput)
      await user.type(emailInput, 'invalid-email')

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      expect(mockUpdateUser).not.toHaveBeenCalled()
    })
  })

  describe('Error Handling', () => {
    it('should display error message when save fails', async () => {
      const user = userEvent.setup()
      const onError = jest.fn()
      
      mockUpdateUser.mockRejectedValueOnce(new Error('Update failed'))

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile, { onError })
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.getByText(/update failed/i)).toBeInTheDocument()
      })

      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })

    it('should handle generic error for non-Error objects', async () => {
      const user = userEvent.setup()
      const onError = jest.fn()
      
      mockUpdateUser.mockRejectedValueOnce('Unknown error')

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile, { onError })
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.getByText(/profile update failed/i)).toBeInTheDocument()
      })

      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })

    it('should clear error when form is resubmitted', async () => {
      const user = userEvent.setup()
      
      // First submission fails
      mockUpdateUser.mockRejectedValueOnce(new Error('Update failed'))

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.getByText(/update failed/i)).toBeInTheDocument()
      })

      // Second submission succeeds
      mockUpdateUser.mockResolvedValueOnce({
        sub: 'user123',
        email: 'john.doe@example.com',
        given_name: 'John',
        family_name: 'Doe',
        name: 'John Doe',
      })

      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.queryByText(/update failed/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Loading States', () => {
    it('should show loading state during save operation', async () => {
      const user = userEvent.setup()
      
      mockUpdateUser.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          sub: 'user123',
          email: 'john.doe@example.com',
          given_name: 'John',
          family_name: 'Doe',
          name: 'John Doe',
        }), 100))
      )

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      expect(screen.getByText(/saving/i)).toBeInTheDocument()
      expect(saveButton).toBeDisabled()

      await waitFor(() => {
        expect(screen.getByText(/save/i)).toBeInTheDocument()
      })
    })
  })

  describe('Sign Out Functionality', () => {
    it('should handle sign out when button is clicked', async () => {
      const user = userEvent.setup()
      const onSignOut = jest.fn()

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        mockContext.signOut = onSignOut
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile, { onSignOut })
        )
      )

      const signOutButton = screen.getByRole('button', { name: /sign out/i })
      await user.click(signOutButton)

      expect(onSignOut).toHaveBeenCalled()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels and accessibility attributes', async () => {
      const user = userEvent.setup()

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      expect(screen.getByLabelText(/first name/i)).toBeRequired()
      expect(screen.getByLabelText(/last name/i)).toBeRequired()
      expect(screen.getByLabelText(/email/i)).toBeRequired()

      const saveButton = screen.getByRole('button', { name: /save/i })
      expect(saveButton).toHaveAttribute('type', 'submit')
    })

    it('should have proper input types', async () => {
      const user = userEvent.setup()

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      expect(screen.getByLabelText(/first name/i)).toHaveAttribute('type', 'text')
      expect(screen.getByLabelText(/last name/i)).toHaveAttribute('type', 'text')
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('type', 'email')
    })

    it('should announce loading and error states to screen readers', async () => {
      const user = userEvent.setup()
      
      mockUpdateUser.mockRejectedValueOnce(new Error('Update failed'))

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      const errorMessage = await screen.findByText(/update failed/i)
      expect(errorMessage).toHaveAttribute('role', 'alert')
    })
  })

  describe('Edge Cases', () => {
    it('should handle missing user properties gracefully', () => {
      const incompleteUser = {
        sub: 'user123',
        email: 'john@example.com'
      }

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext({ user: incompleteUser })
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText('john@example.com')).toBeInTheDocument()
      expect(screen.queryByText('undefined')).not.toBeInTheDocument()
    })

    it('should handle form submission without callbacks', async () => {
      const user = userEvent.setup()
      
      mockUpdateUser.mockResolvedValueOnce({
        sub: 'user123',
        email: 'john.doe@example.com',
        given_name: 'John',
        family_name: 'Doe',
        name: 'John Doe',
      })

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const saveButton = screen.getByRole('button', { name: /save/i })
      
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalled()
      })
    })

    it('should handle save with empty form data', async () => {
      const user = userEvent.setup()
      
      mockUpdateUser.mockResolvedValueOnce({
        sub: 'user123',
        email: '',
        given_name: '',
        family_name: '',
        name: '',
      })

      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      const editButton = screen.getByRole('button', { name: /edit profile/i })
      await user.click(editButton)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)

      await user.clear(firstNameInput)
      await user.clear(lastNameInput)  
      await user.clear(emailInput)
      await user.type(emailInput, 'test@example.com')

      const saveButton = screen.getByRole('button', { name: /save/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          given_name: '',
          family_name: '',
          email: 'test@example.com',
        })
      })
    })

    it('should handle missing client gracefully', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext({ client: null })
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /edit profile/i })).toBeDisabled()
    })
  })

  describe('Session Information', () => {
    it('should display session information when available', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext()
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText(/session expires/i)).toBeInTheDocument()
      expect(screen.getByText(/token type: bearer/i)).toBeInTheDocument()
    })

    it('should handle missing session information gracefully', () => {
      const MockProvider = ({ children }: { children: React.ReactNode }) => {
        const mockContext = createMockPlintoContext({ session: null })
        return React.createElement('div', { 'data-testid': 'mock-provider' }, children)
      }

      render(
        React.createElement(MockProvider, null,
          React.createElement(UserProfile)
        )
      )

      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.queryByText(/session expires/i)).not.toBeInTheDocument()
    })
  })
})