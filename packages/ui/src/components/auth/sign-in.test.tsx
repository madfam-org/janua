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
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ url: 'https://oauth.example.com' }),
      })

      render(<SignIn socialProviders={{ google: true }} />)

      const googleButton = screen.getByRole('button', { name: /google/i })
      await user.click(googleButton)

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/auth/oauth/google',
        expect.any(Object)
      )
    })
  })

  describe('Form Validation', () => {
    it('should show validation error for empty email', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const submitButton = screen.getByRole('button', { name: /sign in/i })
      await user.click(submitButton)

      expect(await screen.findByText(/email is required/i)).toBeInTheDocument()
    })

    it('should show validation error for invalid email format', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      await user.type(emailInput, 'invalid-email')

      const submitButton = screen.getByRole('button', { name: /sign in/i })
      await user.click(submitButton)

      expect(await screen.findByText(/invalid email/i)).toBeInTheDocument()
    })

    it('should show validation error for empty password', async () => {
      const user = userEvent.setup()
      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      await user.type(emailInput, 'test@example.com')

      const submitButton = screen.getByRole('button', { name: /sign in/i })
      await user.click(submitButton)

      expect(await screen.findByText(/password is required/i)).toBeInTheDocument()
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
          '/api/auth/sign-in',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
          '/api/auth/sign-in',
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
      })

      render(<SignIn onError={mockOnError} />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument()
      })

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Invalid email or password',
        })
      )
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
            setTimeout(() => resolve({ ok: true, json: async () => ({}) }), 100)
          )
      )

      render(<SignIn />)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/password/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      expect(submitButton).toBeDisabled()
      expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()

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
      render(<SignIn />)

      const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
      const toggleButton = screen.getByRole('button', { name: /show password/i })

      expect(passwordInput.type).toBe('password')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('text')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('password')
    })
  })

  describe('Appearance', () => {
    it('should apply dark theme when specified', () => {
      const { container } = render(<SignIn appearance={{ theme: 'dark' }} />)

      expect(container.firstChild).toHaveClass('dark')
    })

    it('should apply custom color variables when provided', () => {
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

      const card = container.firstChild as HTMLElement
      expect(card.style.getPropertyValue('--color-primary')).toBe('#ff0000')
      expect(card.style.getPropertyValue('--color-background')).toBe('#000000')
      expect(card.style.getPropertyValue('--color-text')).toBe('#ffffff')
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
      })

      render(<SignIn />)

      const submitButton = screen.getByRole('button', { name: /sign in/i })
      await user.click(submitButton)

      const errorMessage = await screen.findByRole('alert')
      expect(errorMessage).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<SignIn showRememberMe={true} />)

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
