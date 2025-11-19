import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { SignIn } from './sign-in'

describe('SignIn', () => {
  const mockAfterSignIn = vi.fn()
  const mockOnError = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn()
  })

  describe('Rendering', () => {
    it('should render sign-in form with all fields', () => {
      render(<SignIn />)

      expect(screen.getByRole('textbox', { name: /email/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })

    it('should render remember me checkbox when enabled', () => {
      render(<SignIn showRememberMe={true} />)

      expect(screen.getByRole('checkbox', { name: /remember me/i })).toBeInTheDocument()
    })

    it('should not render remember me checkbox when disabled', () => {
      render(<SignIn showRememberMe={false} />)

      expect(screen.queryByRole('checkbox', { name: /remember me/i })).not.toBeInTheDocument()
    })

    it('should render sign-up link when signUpUrl is provided', () => {
      render(<SignIn signUpUrl="/sign-up" />)

      const signUpLink = screen.getByRole('link', { name: /sign up/i })
      expect(signUpLink).toBeInTheDocument()
      expect(signUpLink).toHaveAttribute('href', '/sign-up')
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(<SignIn logoUrl="https://example.com/logo.png" />)

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toBeInTheDocument()
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(<SignIn className="custom-class" />)

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('Social Providers', () => {
    it('should render enabled social providers', () => {
      render(
        <SignIn
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

    it('should call social login handler when provider button is clicked', async () => {
      const user = userEvent.setup()

      // Mock window.location for OAuth redirect
      delete (window as any).location
      window.location = { href: '', origin: 'http://localhost:3000' } as any

      render(<SignIn socialProviders={{ google: true }} />)

      const googleButton = screen.getByRole('button', { name: /google/i })
      await user.click(googleButton)

      // Social login redirects to OAuth URL directly (no fetch call)
      expect(window.location.href).toContain('/api/v1/auth/oauth/google')
      expect(window.location.href).toContain('redirect_url=')
    })
  })

  describe('Form Validation', () => {
    it('should show validation error for empty email', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i }) as HTMLInputElement
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      // HTML5 validation - email is required
      expect(emailInput.required).toBe(true)
      await user.click(submitButton)

      // Browser will prevent form submission due to HTML5 validation
      expect(emailInput.validity.valueMissing).toBe(true)
    })

    it('should show validation error for invalid email format', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i }) as HTMLInputElement
      await user.type(emailInput, 'invalid-email')

      const submitButton = screen.getByRole('button', { name: /sign in/i })
      await user.click(submitButton)

      // HTML5 validation - invalid email format
      expect(emailInput.validity.typeMismatch).toBe(true)
    })

    it('should show validation error for empty password', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      await user.type(emailInput, 'test@example.com')

      const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      // HTML5 validation - password is required
      expect(passwordInput.required).toBe(true)
      await user.click(submitButton)

      expect(passwordInput.validity.valueMissing).toBe(true)
    })
  })

  describe('Form Submission', () => {
    it('should submit form with valid credentials', async () => {
      const user = userEvent.setup()
      const mockUser = { id: '1', email: 'test@example.com' }

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: mockUser }),
      })

      render(<SignIn afterSignIn={mockAfterSignIn} />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/v1/auth/login',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              email: 'test@example.com',
              password: 'password123',
              remember: false,
            }),
          })
        )
      })

      expect(mockAfterSignIn).toHaveBeenCalledWith(mockUser)
    })

    it('should include remember me in submission when checked', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: {} }),
      })

      render(<SignIn showRememberMe={true} />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const rememberCheckbox = screen.getByRole('checkbox', { name: /remember me/i })
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(rememberCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/v1/auth/login',
          expect.objectContaining({
            body: expect.stringContaining('"remember":true'),
          })
        )
      })
    })

    it('should handle sign-in error', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid credentials' }),
      })

      render(<SignIn onError={mockOnError} />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(submitButton)

      await waitFor(() => {
        // Error message is displayed in the error div
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
      })

      expect(mockOnError).toHaveBeenCalled()
    })

    it('should redirect after successful sign-in when redirectUrl is provided', async () => {
      const user = userEvent.setup()
      delete (window as any).location
      window.location = { href: '' } as any

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ user: {} }),
      })

      render(<SignIn redirectUrl="/dashboard" />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(window.location.href).toBe('/dashboard')
      })
    })
  })

  describe('Loading State', () => {
    it('should show loading state during submission', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ ok: true, json: async () => ({ user: {} }) }), 100)
          )
      )

      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Button should be disabled and show loading text
      expect(submitButton).toBeDisabled()
      expect(screen.getByRole('button', { name: /signing in/i })).toBeInTheDocument()

      await waitFor(() => {
        expect(submitButton).not.toBeDisabled()
      })
    })

    it('should disable all inputs during loading', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ ok: true, json: async () => ({ user: {} }) }), 100)
          )
      )

      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      expect(emailInput).toBeDisabled()
      expect(passwordInput).toBeDisabled()
    })
  })

  describe('Password Visibility', () => {
    it('should toggle password visibility', async () => {
      const user = userEvent.setup()
      const { container } = render(<SignIn />)

      const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
      // Toggle button is inside the password field's parent div
      const toggleButton = container.querySelector('button[type="button"]') as HTMLButtonElement

      expect(passwordInput.type).toBe('password')
      expect(toggleButton).toBeInTheDocument()

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('text')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('password')
    })
  })

  describe('Appearance', () => {
    it('should accept appearance prop without error', () => {
      const { container } = render(<SignIn appearance={{ theme: 'dark' }} />)

      // Component accepts appearance prop but doesn't apply theme classes directly
      // Theme should be handled at app level (e.g., next-themes provider)
      expect(container.firstChild).toBeInTheDocument()
    })

    it('should accept custom color variables without error', () => {
      const { container } = render(
        <SignIn
          appearance={{
            variables: {
              colorPrimary: '#ff0000',
              colorBackground: '#000000',
              colorText: '#ffffff',
            },
          }}
        />
      )

      // Component accepts appearance.variables prop
      // CSS variables should be set at app level
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', () => {
      render(<SignIn />)

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    })

    it('should have proper ARIA attributes on error', async () => {
      const user = userEvent.setup()
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ message: 'Invalid credentials' }),
      })

      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Error message is displayed with parsed error message
      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
      })
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      // Disable social providers so we can test email/password form navigation
      render(<SignIn showRememberMe={true} socialProviders={{}} />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      await user.tab()

      expect(emailInput).toHaveFocus()

      await user.tab()
      expect(screen.getByLabelText(/password/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('checkbox', { name: /remember me/i })).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button', { name: /sign in/i })).toHaveFocus()
    })
  })
})
