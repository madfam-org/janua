import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { EmailVerification } from './email-verification'

describe('EmailVerification', () => {
  const mockOnVerify = vi.fn()
  const mockOnResendEmail = vi.fn()
  const mockOnError = vi.fn()
  const mockOnComplete = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Rendering', () => {
    it('should render email verification component', () => {
      render(
        <EmailVerification email="test@example.com" />
      )

      expect(screen.getByText('Verify your email')).toBeInTheDocument()
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(
        <EmailVerification
          email="test@example.com"
          logoUrl="https://example.com/logo.png"
        />
      )

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <EmailVerification
          email="test@example.com"
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('Pending State', () => {
    it('should display pending state by default', () => {
      render(
        <EmailVerification email="test@example.com" />
      )

      expect(screen.getByText('Verify your email')).toBeInTheDocument()
      expect(screen.getByText(/We've sent a verification email/i)).toBeInTheDocument()
      expect(screen.getByText('Check your inbox')).toBeInTheDocument()
    })

    it('should show resend button when enabled', () => {
      render(
        <EmailVerification
          email="test@example.com"
          showResend={true}
          onResendEmail={mockOnResendEmail}
        />
      )

      expect(screen.getByText('Resend verification email')).toBeInTheDocument()
    })

    it('should not show resend button when disabled', () => {
      render(
        <EmailVerification
          email="test@example.com"
          showResend={false}
        />
      )

      expect(screen.queryByText('Resend verification email')).not.toBeInTheDocument()
    })

    it('should display helpful tips', () => {
      render(
        <EmailVerification email="test@example.com" />
      )

      expect(screen.getByText(/Check your spam or junk folder/i)).toBeInTheDocument()
      expect(screen.getByText(/Make sure you entered the correct email/i)).toBeInTheDocument()
    })
  })

  describe('Auto-Verification', () => {
    it('should auto-verify when token is provided', async () => {
      mockOnVerify.mockResolvedValue(undefined)

      render(
        <EmailVerification
          email="test@example.com"
          token="valid-token-123"
          onVerify={mockOnVerify}
          onComplete={mockOnComplete}
        />
      )

      await waitFor(() => {
        expect(mockOnVerify).toHaveBeenCalledWith('valid-token-123')
      })

      await waitFor(() => {
        expect(screen.getByText('Email verified!')).toBeInTheDocument()
        expect(mockOnComplete).toHaveBeenCalled()
      })
    })

    it('should show verifying state during token verification', async () => {
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(
        <EmailVerification
          email="test@example.com"
          token="valid-token-123"
          onVerify={mockOnVerify}
        />
      )

      expect(screen.getByText('Verifying your email')).toBeInTheDocument()
      expect(screen.getByText(/Please wait while we verify/i)).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText('Verifying your email')).not.toBeInTheDocument()
      })
    })

    it('should handle verification error', async () => {
      const error = new Error('Invalid verification token')
      mockOnVerify.mockRejectedValue(error)

      render(
        <EmailVerification
          email="test@example.com"
          token="invalid-token"
          onVerify={mockOnVerify}
          onError={mockOnError}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Verification failed')).toBeInTheDocument()
        expect(screen.getByText('Invalid verification token')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Resend Email', () => {
    it('should resend verification email', async () => {
      const user = userEvent.setup({ delay: null })
      mockOnResendEmail.mockResolvedValue(undefined)

      render(
        <EmailVerification
          email="test@example.com"
          showResend={true}
          onResendEmail={mockOnResendEmail}
        />
      )

      const resendButton = screen.getByText('Resend verification email')
      await user.click(resendButton)

      await waitFor(() => {
        expect(mockOnResendEmail).toHaveBeenCalled()
      })
    })

    it('should show cooldown after resending', async () => {
      const user = userEvent.setup({ delay: null })
      mockOnResendEmail.mockResolvedValue(undefined)

      render(
        <EmailVerification
          email="test@example.com"
          showResend={true}
          onResendEmail={mockOnResendEmail}
        />
      )

      const resendButton = screen.getByText('Resend verification email')
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/Resend in 60s/i)).toBeInTheDocument()
      })

      // Fast-forward time
      vi.advanceTimersByTime(1000)
      await waitFor(() => {
        expect(screen.getByText(/Resend in 59s/i)).toBeInTheDocument()
      })

      // Fast-forward to end of cooldown
      vi.advanceTimersByTime(59000)
      await waitFor(() => {
        expect(screen.getByText('Resend verification email')).toBeInTheDocument()
      })
    })

    it('should disable resend button during cooldown', async () => {
      const user = userEvent.setup({ delay: null })
      mockOnResendEmail.mockResolvedValue(undefined)

      render(
        <EmailVerification
          email="test@example.com"
          showResend={true}
          onResendEmail={mockOnResendEmail}
        />
      )

      const resendButton = screen.getByText('Resend verification email')
      await user.click(resendButton)

      await waitFor(() => {
        const button = screen.getByText(/Resend in/i)
        expect(button).toBeDisabled()
      })
    })

    it('should handle resend error', async () => {
      const user = userEvent.setup({ delay: null })
      const error = new Error('Failed to resend email')
      mockOnResendEmail.mockRejectedValue(error)

      render(
        <EmailVerification
          email="test@example.com"
          showResend={true}
          onResendEmail={mockOnResendEmail}
          onError={mockOnError}
        />
      )

      const resendButton = screen.getByText('Resend verification email')
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText('Failed to resend email')).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })

  describe('Success State', () => {
    it('should display success state', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="success"
        />
      )

      expect(screen.getByText('Email verified!')).toBeInTheDocument()
      expect(screen.getByText(/successfully verified/i)).toBeInTheDocument()
    })

    it('should show continue button when onComplete is provided', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="success"
          onComplete={mockOnComplete}
        />
      )

      expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument()
    })

    it('should call onComplete when clicking continue', async () => {
      const user = userEvent.setup()
      render(
        <EmailVerification
          email="test@example.com"
          status="success"
          onComplete={mockOnComplete}
        />
      )

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      expect(mockOnComplete).toHaveBeenCalled()
    })
  })

  describe('Error State', () => {
    it('should display error state', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="error"
        />
      )

      expect(screen.getByText('Verification failed')).toBeInTheDocument()
      expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument()
    })

    it('should show custom error message', async () => {
      const error = new Error('Custom error message')
      mockOnVerify.mockRejectedValue(error)

      render(
        <EmailVerification
          email="test@example.com"
          token="invalid-token"
          onVerify={mockOnVerify}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Custom error message')).toBeInTheDocument()
      })
    })

    it('should show resend option in error state', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="error"
          showResend={true}
          onResendEmail={mockOnResendEmail}
        />
      )

      expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument()
    })

    it('should display common issues tips', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="error"
        />
      )

      expect(screen.getByText('Common issues')).toBeInTheDocument()
      expect(screen.getByText(/link may have expired/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible success message', () => {
      render(
        <EmailVerification
          email="test@example.com"
          status="success"
        />
      )

      const successHeading = screen.getByText('Email verified!')
      expect(successHeading).toBeInTheDocument()
    })

    it('should support keyboard interaction with buttons', async () => {
      const user = userEvent.setup()
      render(
        <EmailVerification
          email="test@example.com"
          status="success"
          onComplete={mockOnComplete}
        />
      )

      await user.tab()
      const continueButton = screen.getByRole('button', { name: /continue/i })
      expect(continueButton).toHaveFocus()

      await user.keyboard('{Enter}')
      expect(mockOnComplete).toHaveBeenCalled()
    })
  })
})
