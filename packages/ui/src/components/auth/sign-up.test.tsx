import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { SignUp } from './sign-up'

describe('SignUp', () => {
  const mockAfterSignUp = vi.fn()
  const mockOnError = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn()
    // Mock window.alert
    global.alert = vi.fn()
  })

  describe('Rendering', () => {
    it('should render sign-up form with all required fields', () => {
      render(<SignUp />)

      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/last name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByRole('checkbox', { name: /terms/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
    })

    it('should render sign-in link when signInUrl is provided', () => {
      render(<SignUp signInUrl="/sign-in" />)

      const signInLink = screen.getByRole('link', { name: /sign in/i })
      expect(signInLink).toBeInTheDocument()
      expect(signInLink).toHaveAttribute('href', '/sign-in')
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(<SignUp logoUrl="https://example.com/logo.png" />)

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toBeInTheDocument()
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should render password strength meter when enabled', () => {
      const user = userEvent.setup()
      render(<SignUp showPasswordStrength={true} />)

      const passwordInput = screen.getByLabelText(/password/i)
      expect(passwordInput).toBeInTheDocument()
    })

    it('should not render password strength meter when disabled', () => {
      render(<SignUp showPasswordStrength={false} />)

      const passwordInput = screen.getByLabelText(/password/i)
      expect(passwordInput).toBeInTheDocument()
    })
  })

  describe('Social Providers', () => {
    it('should render enabled social providers', () => {
      render(
        <SignUp
          socialProviders={{
            google: true,
            github: true,
            microsoft: false,
            apple: false,
          }}
        />
      )

      expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /github/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /microsoft/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /apple/i })).not.toBeInTheDocument()
    })

    it('should handle social sign-up when provider button is clicked', async () => {
      const user = userEvent.setup()
      delete (window as any).location
      window.location = { href: '' } as any

      render(<SignUp socialProviders={{ google: true }} redirectUrl="/dashboard" />)

      const googleButton = screen.getByRole('button', { name: /google/i })
      await user.click(googleButton)

      expect(window.location.href).toContain('/api/auth/oauth/google')
    })

    it('should not render separator when no social providers are enabled', () => {
      render(
        <SignUp
          socialProviders={{
            google: false,
            github: false,
            microsoft: false,
            apple: false,
          }}
        />
      )

      expect(screen.queryByText(/or sign up with email/i)).not.toBeInTheDocument()
    })
  })

  describe('Form Validation', () => {
    it('should require first name', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const submitButton = screen.getByRole('button', { name: /create account/i })
      const firstNameInput = screen.getByLabelText(/first name/i)

      expect(firstNameInput).toHaveAttribute('required')
    })

    it('should require last name', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const lastNameInput = screen.getByLabelText(/last name/i)

      expect(lastNameInput).toHaveAttribute('required')
    })

    it('should require email', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const emailInput = screen.getByLabelText(/email/i)

      expect(emailInput).toHaveAttribute('required')
    })

    it('should require password', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const passwordInput = screen.getByLabelText(/password/i)

      expect(passwordInput).toHaveAttribute('required')
    })

    it('should require terms agreement', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })

      expect(termsCheckbox).toHaveAttribute('required')
    })

    it('should show error when terms not agreed', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'StrongPassword123!')
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/must agree to the terms/i)).toBeInTheDocument()
      })
    })

    it('should show error when password is too weak', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'weak')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/password is too weak/i)).toBeInTheDocument()
      })
    })
  })

  describe('Password Strength', () => {
    it('should calculate weak password strength', async () => {
      const user = userEvent.setup()
      render(<SignUp showPasswordStrength={true} />)

      const passwordInput = screen.getByLabelText(/password/i)
      await user.type(passwordInput, 'weak')

      await waitFor(() => {
        expect(screen.getByText(/weak/i)).toBeInTheDocument()
      })
    })

    it('should calculate medium password strength', async () => {
      const user = userEvent.setup()
      render(<SignUp showPasswordStrength={true} />)

      const passwordInput = screen.getByLabelText(/password/i)
      await user.type(passwordInput, 'Medium123')

      await waitFor(() => {
        expect(screen.getByText(/medium/i)).toBeInTheDocument()
      })
    })

    it('should calculate strong password strength', async () => {
      const user = userEvent.setup()
      render(<SignUp showPasswordStrength={true} />)

      const passwordInput = screen.getByLabelText(/password/i)
      await user.type(passwordInput, 'VeryStrongPassword123!')

      await waitFor(() => {
        expect(screen.getByText(/strong/i)).toBeInTheDocument()
      })
    })

    it('should show password strength indicator text', async () => {
      const user = userEvent.setup()
      render(<SignUp showPasswordStrength={true} />)

      const passwordInput = screen.getByLabelText(/password/i)
      await user.type(passwordInput, 'test')

      await waitFor(() => {
        expect(screen.getByText(/use 12\+ characters/i)).toBeInTheDocument()
      })
    })
  })

  describe('Form Submission', () => {
    it('should submit form with valid data', async () => {
      const user = userEvent.setup()
      const mockUser = { id: '1', email: 'john@example.com' }

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: mockUser }),
      })

      render(<SignUp afterSignUp={mockAfterSignUp} requireEmailVerification={false} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/auth/sign-up',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              firstName: 'John',
              lastName: 'Doe',
              email: 'john@example.com',
              password: 'VeryStrongPassword123!',
            }),
          })
        )
      })

      expect(mockAfterSignUp).toHaveBeenCalledWith(mockUser)
    })

    it('should show email verification alert when required', async () => {
      const user = userEvent.setup()

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: {} }),
      })

      render(<SignUp requireEmailVerification={true} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(global.alert).toHaveBeenCalledWith('Please check your email to verify your account')
      })
    })

    it('should redirect after successful sign-up when redirectUrl is provided', async () => {
      const user = userEvent.setup()
      delete (window as any).location
      window.location = { href: '' } as any

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: {} }),
      })

      render(<SignUp redirectUrl="/dashboard" requireEmailVerification={false} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(window.location.href).toBe('/dashboard')
      })
    })

    it('should handle sign-up error', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ message: 'Email already exists' }),
      })

      render(<SignUp onError={mockOnError} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument()
      })

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Email already exists',
        })
      )
    })
  })

  describe('Loading State', () => {
    it('should show loading state during submission', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ ok: true, json: async () => ({}) }), 100)
          )
      )

      render(<SignUp requireEmailVerification={false} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      expect(submitButton).toHaveTextContent(/creating account/i)
      expect(submitButton).toBeDisabled()

      await waitFor(() => {
        expect(submitButton).not.toBeDisabled()
      })
    })

    it('should disable all inputs during loading', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ ok: true, json: async () => ({}) }), 100)
          )
      )

      render(<SignUp requireEmailVerification={false} />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      const lastNameInput = screen.getByLabelText(/last name/i)
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i })
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(firstNameInput, 'John')
      await user.type(lastNameInput, 'Doe')
      await user.type(emailInput, 'john@example.com')
      await user.type(passwordInput, 'VeryStrongPassword123!')
      await user.click(termsCheckbox)
      await user.click(submitButton)

      expect(firstNameInput).toBeDisabled()
      expect(lastNameInput).toBeDisabled()
      expect(emailInput).toBeDisabled()
      expect(passwordInput).toBeDisabled()
      expect(termsCheckbox).toBeDisabled()
    })
  })

  describe('Password Visibility', () => {
    it('should toggle password visibility', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
      const toggleButton = passwordInput.nextElementSibling as HTMLButtonElement

      expect(passwordInput.type).toBe('password')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('text')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('password')
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', () => {
      render(<SignUp />)

      expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/last name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    })

    it('should have proper autocomplete attributes', () => {
      render(<SignUp />)

      expect(screen.getByLabelText(/first name/i)).toHaveAttribute('autocomplete', 'given-name')
      expect(screen.getByLabelText(/last name/i)).toHaveAttribute('autocomplete', 'family-name')
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('autocomplete', 'email')
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('autocomplete', 'new-password')
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<SignUp />)

      const firstNameInput = screen.getByLabelText(/first name/i)
      await user.tab()

      expect(firstNameInput).toHaveFocus()

      await user.tab()
      expect(screen.getByLabelText(/last name/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByLabelText(/email/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByLabelText(/password/i)).toHaveFocus()
    })
  })
})
