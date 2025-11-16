import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { MFAChallenge } from './mfa-challenge'

describe('MFAChallenge', () => {
  const mockOnVerify = vi.fn()
  const mockOnUseBackupCode = vi.fn()
  const mockOnRequestNewCode = vi.fn()
  const mockOnError = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  describe('Rendering', () => {
    it('should render MFA challenge form', () => {
      render(<MFAChallenge />)

      expect(screen.getByText(/two-factor authentication/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /verify/i })).toBeInTheDocument()
    })

    it('should display user email when provided', () => {
      render(<MFAChallenge userEmail="john@example.com" />)

      expect(screen.getByText(/john@example.com/i)).toBeInTheDocument()
    })

    it('should show TOTP method description', () => {
      render(<MFAChallenge method="totp" />)

      expect(screen.getByText(/authenticator app/i)).toBeInTheDocument()
    })

    it('should show SMS method description', () => {
      render(<MFAChallenge method="sms" />)

      expect(screen.getByText(/your phone/i)).toBeInTheDocument()
    })

    it('should show backup code option when enabled', () => {
      render(<MFAChallenge showBackupCodeOption={true} onUseBackupCode={mockOnUseBackupCode} />)

      expect(screen.getByRole('button', { name: /use a backup code/i })).toBeInTheDocument()
    })

    it('should not show backup code option when disabled', () => {
      render(<MFAChallenge showBackupCodeOption={false} />)

      expect(screen.queryByRole('button', { name: /use a backup code/i })).not.toBeInTheDocument()
    })

    it('should show resend option for SMS when enabled', () => {
      render(<MFAChallenge method="sms" allowResend={true} />)

      expect(screen.getByRole('button', { name: /resend code/i })).toBeInTheDocument()
    })

    it('should not show resend option for TOTP', () => {
      render(<MFAChallenge method="totp" allowResend={true} />)

      expect(screen.queryByRole('button', { name: /resend code/i })).not.toBeInTheDocument()
    })
  })

  describe('Code Input', () => {
    it('should only accept numeric input', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, 'abc123def')

      expect(codeInput).toHaveValue('123')
    })

    it('should limit input to 6 digits', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '1234567890')

      expect(codeInput).toHaveValue('123456')
    })

    it('should have autofocus on code input', () => {
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('autofocus')
    })

    it('should have proper autocomplete attribute', () => {
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('autocomplete', 'one-time-code')
    })

    it('should have numeric input mode', () => {
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('inputmode', 'numeric')
    })
  })

  describe('Form Submission', () => {
    it('should verify code on submit', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockResolvedValue(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(mockOnVerify).toHaveBeenCalledWith('123456')
      })
    })

    it('should auto-submit when 6 digits are entered', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockResolvedValue(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(mockOnVerify).toHaveBeenCalledWith('123456')
      })
    })

    it('should disable verify button when code is incomplete', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      expect(verifyButton).toBeDisabled()

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '12345')
      expect(verifyButton).toBeDisabled()

      await user.type(codeInput, '6')
      expect(verifyButton).not.toBeDisabled()
    })

    it('should show loading state during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })

      await waitFor(() => {
        expect(verifyButton).toHaveTextContent(/verifying/i)
        expect(verifyButton).toBeDisabled()
      })
    })

    it('should show error on invalid code', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid verification code'))

      render(<MFAChallenge onVerify={mockOnVerify} onError={mockOnError} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      await waitFor(() => {
        expect(screen.getByText(/invalid verification code/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should clear code on error', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      await waitFor(() => {
        expect(codeInput).toHaveValue('')
      })
    })

    it('should track failed attempts', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)

      // First attempt
      await user.type(codeInput, '000001')
      await waitFor(() => expect(codeInput).toHaveValue(''))

      // Second attempt
      await user.type(codeInput, '000002')
      await waitFor(() => expect(codeInput).toHaveValue(''))

      // Third attempt - should show help message
      await user.type(codeInput, '000003')
      await waitFor(() => {
        expect(screen.getByText(/having trouble/i)).toBeInTheDocument()
      })
    })
  })

  describe('Resend Code (SMS)', () => {
    it('should resend code when button is clicked', async () => {
      const user = userEvent.setup()
      mockOnRequestNewCode.mockResolvedValue(undefined)

      render(<MFAChallenge method="sms" allowResend={true} onRequestNewCode={mockOnRequestNewCode} />)

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(mockOnRequestNewCode).toHaveBeenCalled()
      })
    })

    it('should start cooldown after resending', async () => {
      const user = userEvent.setup()
      vi.useFakeTimers()
      mockOnRequestNewCode.mockResolvedValue(undefined)

      render(<MFAChallenge method="sms" allowResend={true} onRequestNewCode={mockOnRequestNewCode} />)

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/resend code in 60s/i)).toBeInTheDocument()
      })

      vi.advanceTimersByTime(10000)

      await waitFor(() => {
        expect(screen.getByText(/resend code in 50s/i)).toBeInTheDocument()
      })

      vi.useRealTimers()
    })

    it('should disable resend button during cooldown', async () => {
      const user = userEvent.setup()
      vi.useFakeTimers()
      mockOnRequestNewCode.mockResolvedValue(undefined)

      render(<MFAChallenge method="sms" allowResend={true} onRequestNewCode={mockOnRequestNewCode} />)

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(resendButton).toBeDisabled()
      })

      vi.advanceTimersByTime(60000)

      await waitFor(() => {
        expect(resendButton).not.toBeDisabled()
      })

      vi.useRealTimers()
    })

    it('should show error when resend fails', async () => {
      const user = userEvent.setup()
      mockOnRequestNewCode.mockRejectedValue(new Error('Failed to resend code'))

      render(
        <MFAChallenge
          method="sms"
          allowResend={true}
          onRequestNewCode={mockOnRequestNewCode}
          onError={mockOnError}
        />
      )

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/failed to resend code/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })
  })

  describe('Backup Code Option', () => {
    it('should call onUseBackupCode when backup code button is clicked', async () => {
      const user = userEvent.setup()

      render(<MFAChallenge showBackupCodeOption={true} onUseBackupCode={mockOnUseBackupCode} />)

      const backupCodeButton = screen.getByRole('button', { name: /use a backup code/i })
      await user.click(backupCodeButton)

      expect(mockOnUseBackupCode).toHaveBeenCalled()
    })

    it('should not render backup code option when callback not provided', () => {
      render(<MFAChallenge showBackupCodeOption={true} />)

      expect(screen.queryByRole('button', { name: /use a backup code/i })).not.toBeInTheDocument()
    })
  })

  describe('Help Section', () => {
    it('should display help text', () => {
      render(<MFAChallenge />)

      expect(screen.getByText(/need help/i)).toBeInTheDocument()
      expect(screen.getByText(/make sure your authenticator app is synced/i)).toBeInTheDocument()
      expect(screen.getByText(/the code expires after 30 seconds/i)).toBeInTheDocument()
      expect(screen.getByText(/lost access to your authenticator/i)).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('should disable input during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(codeInput).toBeDisabled()
      })
    })

    it('should show loading spinner during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        const spinner = document.querySelector('.animate-spin')
        expect(spinner).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', () => {
      render(<MFAChallenge />)

      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
    })

    it('should have error role on error message', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      await waitFor(() => {
        const errorContainer = screen.getByText(/invalid code/i).closest('div')
        expect(errorContainer).toHaveClass('bg-destructive/15')
      })
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge showBackupCodeOption={true} onUseBackupCode={mockOnUseBackupCode} />)

      await user.tab()
      expect(screen.getByLabelText(/verification code/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button', { name: /verify/i })).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button', { name: /use a backup code/i })).toHaveFocus()
    })

    it('should have descriptive helper text', () => {
      render(<MFAChallenge />)

      expect(screen.getByText(/enter the 6-digit code/i)).toBeInTheDocument()
    })
  })

  describe('Visual States', () => {
    it('should style code input for readability', () => {
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveClass('text-center', 'text-2xl', 'tracking-widest')
    })

    it('should show icon in header', () => {
      const { container } = render(<MFAChallenge />)

      const icon = container.querySelector('svg')
      expect(icon).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('should handle missing onVerify gracefully', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      // Should not throw
      expect(() => {
        const verifyButton = screen.getByRole('button', { name: /verify/i })
        verifyButton.click()
      }).not.toThrow()
    })

    it('should handle missing onError gracefully', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Test error'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      await waitFor(() => {
        expect(screen.getByText(/test error/i)).toBeInTheDocument()
      })
    })

    it('should clear error on new submission attempt', async () => {
      const user = userEvent.setup()
      mockOnVerify
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const codeInput = screen.getByLabelText(/verification code/i)

      // First attempt - error
      await user.type(codeInput, '000000')
      await waitFor(() => {
        expect(screen.getByText(/first error/i)).toBeInTheDocument()
      })

      // Second attempt - success
      await user.type(codeInput, '123456')
      await waitFor(() => {
        expect(screen.queryByText(/first error/i)).not.toBeInTheDocument()
      })
    })
  })
})
