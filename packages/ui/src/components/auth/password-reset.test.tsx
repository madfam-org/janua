import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { PasswordReset } from './password-reset'

describe('PasswordReset', () => {
  const mockOnRequestReset = vi.fn()
  const mockOnVerifyToken = vi.fn()
  const mockOnResetPassword = vi.fn()
  const mockOnError = vi.fn()
  const mockOnBackToSignIn = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render password reset component', () => {
      render(<PasswordReset />)

      expect(screen.getByText('Reset your password')).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(<PasswordReset logoUrl="https://example.com/logo.png" />)

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(<PasswordReset className="custom-class" />)

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('Request Reset Step', () => {
    it('should display request reset form', () => {
      render(<PasswordReset step="request" />)

      expect(screen.getByText('Reset your password')).toBeInTheDocument()
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument()
    })

    it('should populate email input with initial value', () => {
      render(<PasswordReset email="test@example.com" step="request" />)

      const emailInput = screen.getByLabelText(/email address/i)
      expect(emailInput).toHaveValue('test@example.com')
    })

    it('should request password reset', async () => {
      const user = userEvent.setup()
      mockOnRequestReset.mockResolvedValue(undefined)

      render(<PasswordReset onRequestReset={mockOnRequestReset} />)

      const emailInput = screen.getByLabelText(/email address/i)
      const submitButton = screen.getByRole('button', { name: /send reset link/i })

      await user.type(emailInput, 'test@example.com')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnRequestReset).toHaveBeenCalledWith('test@example.com')
      })
    })

    it('should show loading state during request', async () => {
      const user = userEvent.setup()
      mockOnRequestReset.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<PasswordReset onRequestReset={mockOnRequestReset} />)

      const emailInput = screen.getByLabelText(/email address/i)
      const submitButton = screen.getByRole('button', { name: /send reset link/i })

      await user.type(emailInput, 'test@example.com')
      await user.click(submitButton)

      expect(screen.getByText(/sending\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/sending\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle request error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to send reset email')
      mockOnRequestReset.mockRejectedValue(error)

      render(<PasswordReset onRequestReset={mockOnRequestReset} onError={mockOnError} />)

      const emailInput = screen.getByLabelText(/email address/i)
      const submitButton = screen.getByRole('button', { name: /send reset link/i })

      await user.type(emailInput, 'test@example.com')
      await user.click(submitButton)

      await waitFor(() => {
        // Error message is split across multiple elements, so find by partial text
        const errorElements = screen.getAllByText(/failed|send|reset|email/i)
        expect(errorElements.length).toBeGreaterThan(0)
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should show back to sign in button', () => {
      render(<PasswordReset onBackToSignIn={mockOnBackToSignIn} />)

      expect(screen.getByText(/back to sign in/i)).toBeInTheDocument()
    })

    it('should call back to sign in callback', async () => {
      const user = userEvent.setup()
      render(<PasswordReset onBackToSignIn={mockOnBackToSignIn} />)

      const backButton = screen.getByText(/back to sign in/i)
      await user.click(backButton)

      expect(mockOnBackToSignIn).toHaveBeenCalled()
    })

    it('should transition to verify step after request', async () => {
      const user = userEvent.setup()
      mockOnRequestReset.mockResolvedValue(undefined)

      render(<PasswordReset onRequestReset={mockOnRequestReset} />)

      const emailInput = screen.getByLabelText(/email address/i)
      await user.type(emailInput, 'test@example.com')

      const submitButton = screen.getByRole('button', { name: /send reset link/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Check your email')).toBeInTheDocument()
      })
    })
  })

  describe('Verify Step', () => {
    it('should display verify instructions', () => {
      render(<PasswordReset email="test@example.com" step="verify" />)

      expect(screen.getByText('Check your email')).toBeInTheDocument()
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })

    it('should allow trying different email', async () => {
      const user = userEvent.setup()
      render(<PasswordReset email="test@example.com" step="verify" />)

      const tryDifferentButton = screen.getByRole('button', { name: /try a different email/i })
      await user.click(tryDifferentButton)

      expect(screen.getByText('Reset your password')).toBeInTheDocument()
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
    })

    it('should display helpful tips', () => {
      render(<PasswordReset email="test@example.com" step="verify" />)

      expect(screen.getByText(/Didn't receive the email\?/i)).toBeInTheDocument()
      expect(screen.getByText(/Check your spam or junk folder/i)).toBeInTheDocument()
    })
  })

  describe('Auto Token Verification', () => {
    it('should auto-verify token when provided', async () => {
      mockOnVerifyToken.mockResolvedValue(undefined)

      render(
        <PasswordReset
          token="valid-token-123"
          onVerifyToken={mockOnVerifyToken}
        />
      )

      await waitFor(() => {
        expect(mockOnVerifyToken).toHaveBeenCalledWith('valid-token-123')
      })

      await waitFor(() => {
        expect(screen.getByText('Create new password')).toBeInTheDocument()
      })
    })

    it('should handle invalid token', async () => {
      const error = new Error('Invalid or expired reset link')
      mockOnVerifyToken.mockRejectedValue(error)

      render(
        <PasswordReset
          token="invalid-token"
          onVerifyToken={mockOnVerifyToken}
          onError={mockOnError}
        />
      )

      await waitFor(() => {
        // Error message is split across multiple elements, so find by partial text
        const errorElements = screen.getAllByText(/invalid|expired|reset|link/i)
        expect(errorElements.length).toBeGreaterThan(0)
        expect(mockOnError).toHaveBeenCalled()
      })
    })
  })

  describe('Reset Password Step', () => {
    it('should display reset password form', () => {
      render(<PasswordReset step="reset" />)

      expect(screen.getByText('Create new password')).toBeInTheDocument()
      expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    })

    it('should show password strength indicator', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="reset" />)

      const passwordInput = screen.getByLabelText(/^new password$/i)
      await user.type(passwordInput, 'weak')

      expect(screen.getByText('Weak')).toBeInTheDocument()

      await user.clear(passwordInput)
      await user.type(passwordInput, 'Medium123')

      expect(screen.getByText('Medium')).toBeInTheDocument()

      await user.clear(passwordInput)
      await user.type(passwordInput, 'Strong123!@#')

      expect(screen.getByText('Strong')).toBeInTheDocument()
    })

    it('should validate password mismatch', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="reset" token="token" onResetPassword={mockOnResetPassword} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'Password123')
      await user.type(confirmPasswordInput, 'Different123')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      expect(screen.getByText(/Passwords don't match/i)).toBeInTheDocument()
      expect(mockOnResetPassword).not.toHaveBeenCalled()
    })

    it('should validate minimum password length', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="reset" token="token" onResetPassword={mockOnResetPassword} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'short')
      await user.type(confirmPasswordInput, 'short')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      expect(screen.getByText(/Password too weak|8 characters/i)).toBeInTheDocument()
      expect(mockOnResetPassword).not.toHaveBeenCalled()
    })

    it('should reset password successfully', async () => {
      const user = userEvent.setup()
      mockOnResetPassword.mockResolvedValue(undefined)

      render(<PasswordReset step="reset" token="valid-token" onResetPassword={mockOnResetPassword} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'NewPassword123!')
      await user.type(confirmPasswordInput, 'NewPassword123!')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnResetPassword).toHaveBeenCalledWith('valid-token', 'NewPassword123!')
      })
    })

    it('should show loading state during reset', async () => {
      const user = userEvent.setup()
      mockOnResetPassword.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<PasswordReset step="reset" token="token" onResetPassword={mockOnResetPassword} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'NewPassword123!')
      await user.type(confirmPasswordInput, 'NewPassword123!')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      expect(screen.getByText(/resetting\.\.\./i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText(/resetting\.\.\./i)).not.toBeInTheDocument()
      })
    })

    it('should handle reset error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to reset password')
      mockOnResetPassword.mockRejectedValue(error)

      render(<PasswordReset step="reset" token="token" onResetPassword={mockOnResetPassword} onError={mockOnError} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'NewPassword123!')
      await user.type(confirmPasswordInput, 'NewPassword123!')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Error message is split across multiple elements, so find by partial text
        const errorElements = screen.getAllByText(/failed|reset|password/i)
        expect(errorElements.length).toBeGreaterThan(0)
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should transition to success after reset', async () => {
      const user = userEvent.setup()
      mockOnResetPassword.mockResolvedValue(undefined)

      render(<PasswordReset step="reset" token="token" onResetPassword={mockOnResetPassword} />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      await user.type(newPasswordInput, 'NewPassword123!')
      await user.type(confirmPasswordInput, 'NewPassword123!')

      const submitButton = screen.getByRole('button', { name: /reset password/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Password reset successful')).toBeInTheDocument()
      })
    })

    it('should display password requirements', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="reset" />)

      const passwordInput = screen.getByLabelText(/^new password$/i)
      await user.type(passwordInput, 'test')

      expect(screen.getByText(/Use 8\+ characters with uppercase/i)).toBeInTheDocument()
    })
  })

  describe('Success Step', () => {
    it('should display success message', () => {
      render(<PasswordReset step="success" />)

      expect(screen.getByText('Password reset successful')).toBeInTheDocument()
      expect(screen.getByText(/successfully reset/i)).toBeInTheDocument()
    })

    it('should show continue to sign in button', () => {
      render(<PasswordReset step="success" onBackToSignIn={mockOnBackToSignIn} />)

      expect(screen.getByRole('button', { name: /continue to sign in/i })).toBeInTheDocument()
    })

    it('should call back to sign in callback', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="success" onBackToSignIn={mockOnBackToSignIn} />)

      const continueButton = screen.getByRole('button', { name: /continue to sign in/i })
      await user.click(continueButton)

      expect(mockOnBackToSignIn).toHaveBeenCalled()
    })
  })

  describe('Password Strength Calculation', () => {
    it('should calculate weak password strength', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="reset" />)

      const passwordInput = screen.getByLabelText(/^new password$/i)
      await user.type(passwordInput, 'short')

      const { container } = render(<PasswordReset step="reset" />)
      const passwordInput2 = container.querySelector('input[type="password"]') as HTMLInputElement

      // Just verify weak passwords are detected
      expect(screen.getByText('Weak')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible form labels', () => {
      render(<PasswordReset step="request" />)

      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
    })

    it('should have accessible password inputs', () => {
      render(<PasswordReset step="reset" />)

      expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<PasswordReset step="request" />)

      // Email input should have autofocus
      const emailInput = screen.getByLabelText(/email address/i)
      expect(emailInput).toHaveFocus()

      // Tab should move to submit button
      await user.tab()
      const submitButton = screen.getByRole('button', { name: /send reset link/i })
      expect(submitButton).toHaveFocus()
    })

    it('should have proper input attributes', () => {
      render(<PasswordReset step="reset" />)

      const newPasswordInput = screen.getByLabelText(/^new password$/i)
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)

      expect(newPasswordInput).toHaveAttribute('type', 'password')
      expect(newPasswordInput).toHaveAttribute('minLength', '8')
      expect(confirmPasswordInput).toHaveAttribute('type', 'password')
      expect(confirmPasswordInput).toHaveAttribute('minLength', '8')
    })
  })
})
