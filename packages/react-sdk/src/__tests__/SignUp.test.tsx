import React from 'react'
import { render, screen, fireEvent as _fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignUp } from '../components/SignUp'
import { JanuaProvider } from '../provider'
import { JanuaClient } from '@janua/typescript-sdk'

// Mock the Janua SDK
jest.mock('@janua/typescript-sdk', () => ({
  JanuaClient: jest.fn().mockImplementation(() => ({
    signUp: jest.fn(),
    signIn: jest.fn(),
    getCurrentUser: jest.fn(),
    signOut: jest.fn(),
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

// Mock window.location
const locationMock = { href: '' }
Object.defineProperty(window, 'location', { 
  value: locationMock,
  writable: true
})

const mockConfig = {
  baseURL: 'https://api.janua.dev',
  apiKey: 'test-key',
}

describe('SignUp Component', () => {
  let mockClient: any
  
  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
    locationMock.href = ''
    mockClient = new JanuaClient(mockConfig)
    ;(JanuaClient as any).mockImplementation(() => mockClient)
  })

  const renderSignUp = (props = {}) => {
    return render(
      React.createElement(
        JanuaProvider,
        { config: mockConfig, children: React.createElement(SignUp, props) }
      )
    )
  }

  describe('Rendering', () => {
    it('should render sign up form with all required fields', () => {
      renderSignUp()
      
      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/last name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      renderSignUp({ className: 'custom-signup-class' })
      
      const container = screen.getByRole('button', { name: /create account/i }).closest('.janua-signup')
      expect(container).toHaveClass('custom-signup-class')
    })

    it('should show organization field when requireOrganization is true', () => {
      renderSignUp({ requireOrganization: true })
      
      expect(screen.getByLabelText(/organization name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/organization name/i)).toBeRequired()
    })

    it('should not show organization field when requireOrganization is false', () => {
      renderSignUp({ requireOrganization: false })
      
      expect(screen.queryByLabelText(/organization name/i)).not.toBeInTheDocument()
    })

    it('should display password requirements hint', () => {
      renderSignUp()
      
      expect(screen.getByText(/at least 8 characters with uppercase, lowercase and numbers/i)).toBeInTheDocument()
    })
  })

  describe('Form Validation', () => {
    it('should require all mandatory fields', async () => {
      const user = userEvent.setup()
      renderSignUp()
      
      const submitButton = screen.getByRole('button', { name: /create account/i })
      await user.click(submitButton)
      
      // HTML5 validation should prevent form submission
      expect(mockClient.signUp).not.toHaveBeenCalled()
    })

    it('should validate email format', async () => {
      const user = userEvent.setup()
      renderSignUp()
      
      const emailInput = screen.getByLabelText(/email/i)
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const passwordInput = screen.getByLabelText(/password/i)
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'invalid-email')
      await user.type(passwordInput, 'Password123')
      
      const submitButton = screen.getByRole('button', { name: /create account/i })
      await user.click(submitButton)
      
      // HTML5 email validation should prevent submission
      expect(mockClient.signUp).not.toHaveBeenCalled()
    })

    it('should require organization when requireOrganization is true', async () => {
      const user = userEvent.setup()
      renderSignUp({ requireOrganization: true })
      
      const submitButton = screen.getByRole('button', { name: /create account/i })
      await user.click(submitButton)
      
      const organizationInput = screen.getByLabelText(/organization name/i)
      expect(organizationInput).toBeRequired()
      expect(mockClient.signUp).not.toHaveBeenCalled()
    })
  })

  describe('Form Input Handling', () => {
    it('should update form data when inputs change', async () => {
      const user = userEvent.setup()
      renderSignUp()
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      
      expect((firstNameInput as HTMLInputElement).value).toBe('John')
      expect((lastNameInput as HTMLInputElement).value).toBe('Doe')
      expect((emailInput as HTMLInputElement).value).toBe('john.doe@example.com')
      expect((passwordInput as HTMLInputElement).value).toBe('Password123')
    })

    it('should handle organization input when required', async () => {
      const user = userEvent.setup()
      renderSignUp({ requireOrganization: true })
      
      const organizationInput = screen.getByLabelText(/organization name/i)
      await user.type(organizationInput, 'Acme Corp')
      
      expect((organizationInput as HTMLInputElement).value).toBe('Acme Corp')
    })
  })

  describe('Form Submission', () => {
    it('should successfully submit registration without email verification', async () => {
      const user = userEvent.setup()
      const onSuccess = jest.fn()
      
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp({ onSuccess, redirectTo: '/dashboard', requireEmailVerification: false })
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(mockClient.signUp).toHaveBeenCalledWith({
          email: 'john.doe@example.com',
          password: 'Password123',
          given_name: 'John',
          family_name: 'Doe',
          name: 'John Doe',
        })
      })

      await waitFor(() => {
        expect(mockClient.signIn).toHaveBeenCalledWith('john.doe@example.com', 'Password123')
      })
      
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })

      expect(locationMock.href).toBe('/dashboard')
    })

    it('should successfully submit registration with email verification', async () => {
      const user = userEvent.setup()
      const onSuccess = jest.fn()
      
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp({ onSuccess, redirectTo: '/dashboard', requireEmailVerification: true })
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(mockClient.signUp).toHaveBeenCalledWith({
          email: 'john.doe@example.com',
          password: 'Password123',
          given_name: 'John',
          family_name: 'Doe',
          name: 'John Doe',
        })
      })

      // Should NOT call signIn when email verification is required
      expect(mockClient.signIn).not.toHaveBeenCalled()
      
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })

      expect(locationMock.href).toBe('/verify-email')
    })

    it('should handle single name gracefully', async () => {
      const user = userEvent.setup()
      
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp()
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, '') // Empty last name
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(mockClient.signUp).toHaveBeenCalledWith({
          email: 'john@example.com',
          password: 'Password123',
          given_name: 'John',
          family_name: '',
          name: 'John',
        })
      })
    })
  })

  describe('Error Handling', () => {
    it('should display registration error message', async () => {
      const user = userEvent.setup()
      const onError = jest.fn()
      
      mockClient.signUp.mockRejectedValueOnce(new Error('Email already exists'))
      
      renderSignUp({ onError })
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'existing@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument()
      })
      
      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })

    it('should handle generic error message for non-Error objects', async () => {
      const user = userEvent.setup()
      const onError = jest.fn()
      
      mockClient.signUp.mockRejectedValueOnce('Unknown error')
      
      renderSignUp({ onError })
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/registration failed/i)).toBeInTheDocument()
      })
      
      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })

    it('should clear error when form is resubmitted', async () => {
      const user = userEvent.setup()
      
      // First submission fails
      mockClient.signUp.mockRejectedValueOnce(new Error('Registration failed'))
      
      renderSignUp()
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(screen.getByText(/registration failed/i)).toBeInTheDocument()
      })
      
      // Second submission succeeds
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(screen.queryByText(/registration failed/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Loading States', () => {
    it('should show loading state during registration', async () => {
      const user = userEvent.setup()
      
      mockClient.signUp.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          token_type: 'Bearer',
          expires_in: 3600,
        }), 100))
      )
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp()
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      await user.click(submitButton)
      
      expect(screen.getByText(/creating account/i)).toBeInTheDocument()
      expect(submitButton).toBeDisabled()
      
      await waitFor(() => {
        expect(screen.getByText(/create account/i)).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels and accessibility attributes', () => {
      renderSignUp()
      
      expect(screen.getByLabelText(/first name/i)).toBeRequired()
      expect(screen.getByLabelText(/last name/i)).toBeRequired()
      expect(screen.getByLabelText(/email/i)).toBeRequired()
      expect(screen.getByLabelText(/password/i)).toBeRequired()
      
      const submitButton = screen.getByRole('button', { name: /create account/i })
      expect(submitButton).toHaveAttribute('type', 'submit')
    })

    it('should have proper input types', () => {
      renderSignUp()
      
      expect(screen.getByLabelText(/first name/i)).toHaveAttribute('type', 'text')
      expect(screen.getByLabelText(/last name/i)).toHaveAttribute('type', 'text')
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('type', 'email')
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password')
    })

    it('should have proper placeholders', () => {
      renderSignUp({ requireOrganization: true })
      
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('placeholder', 'you@example.com')
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('placeholder', '••••••••')
      expect(screen.getByLabelText(/organization name/i)).toHaveAttribute('placeholder', 'Acme Corporation')
    })
  })

  describe('Edge Cases', () => {
    it('should handle form submission without callbacks', async () => {
      const user = userEvent.setup()
      
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp() // No callbacks provided
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      
      // Should not throw error even without callbacks
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(mockClient.signUp).toHaveBeenCalled()
      })
    })

    it('should handle redirect without window object', async () => {
      const user = userEvent.setup()
      const originalWindow = global.window
      
      // Remove window object
      Object.defineProperty(global, 'window', { 
        value: undefined,
        writable: true
      })
      
      mockClient.signUp.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      mockClient.signIn.mockResolvedValueOnce({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'Bearer',
        expires_in: 3600,
      })
      
      renderSignUp({ redirectTo: '/dashboard' })
      
      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })
      
      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john.doe@example.com')
      await user.type(passwordInput, 'Password123')
      
      // Should not throw error even without window
      await user.click(submitButton)
      
      await waitFor(() => {
        expect(mockClient.signUp).toHaveBeenCalled()
      })
      
      // Restore window
      Object.defineProperty(global, 'window', { 
        value: originalWindow,
        writable: true
      })
    })
  })
})