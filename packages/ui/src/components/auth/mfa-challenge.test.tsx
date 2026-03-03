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
      // 6 individual digit inputs
      for (let i = 1; i <= 6; i++) {
        expect(screen.getByLabelText(`Digit ${i}`)).toBeInTheDocument()
      }
      expect(screen.getByRole('button', { name: /verify/i })).toBeInTheDocument()
    })

    it('should display user email when provided', () => {
      render(<MFAChallenge userEmail="john@example.com" />)

      expect(screen.getByText(/john@example.com/i)).toBeInTheDocument()
    })

    it('should show TOTP method description', () => {
      render(<MFAChallenge method="totp" />)

      const elements = screen.getAllByText(/authenticator app/i)
      expect(elements.length).toBeGreaterThan(0)
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
    it('should only accept numeric input in digit fields', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, 'a')

      expect(digit1).toHaveValue('')

      await user.type(digit1, '1')
      expect(digit1).toHaveValue('1')
    })

    it('should auto-advance to next digit on input', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      const digit2 = screen.getByLabelText('Digit 2')

      await user.type(digit1, '1')
      expect(digit2).toHaveFocus()
    })

    it('should have autofocus on first digit input', () => {
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      expect(digit1).toHaveFocus()
    })

    it('should have proper autocomplete attribute on first digit', () => {
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      expect(digit1).toHaveAttribute('autocomplete', 'one-time-code')
    })

    it('should have numeric input mode on digit inputs', () => {
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      expect(digit1).toHaveAttribute('inputmode', 'numeric')
    })

    it('should move back on backspace when current digit is empty', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const digit1 = screen.getByLabelText('Digit 1')
      const digit2 = screen.getByLabelText('Digit 2')

      // Type first digit, auto-advance to digit 2
      await user.type(digit1, '1')
      expect(digit2).toHaveFocus()

      // Backspace on empty digit 2 → clears digit 1 and focuses it
      await user.keyboard('{Backspace}')
      expect(digit1).toHaveFocus()
    })
  })

  describe('Form Submission', () => {
    it('should verify code on submit', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockResolvedValue(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      // Type all 6 digits
      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      const digit2 = screen.getByLabelText('Digit 2')
      await user.type(digit2, '2')
      const digit3 = screen.getByLabelText('Digit 3')
      await user.type(digit3, '3')
      const digit4 = screen.getByLabelText('Digit 4')
      await user.type(digit4, '4')
      const digit5 = screen.getByLabelText('Digit 5')
      await user.type(digit5, '5')
      const digit6 = screen.getByLabelText('Digit 6')
      await user.type(digit6, '6')

      await waitFor(() => {
        expect(mockOnVerify).toHaveBeenCalledWith('123456')
      })
    })

    it('should auto-submit when 6 digits are entered', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockResolvedValue(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      // Type all 6 digits sequentially — auto-advance handles focus
      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      await waitFor(() => {
        expect(mockOnVerify).toHaveBeenCalledWith('123456')
      })
    })

    it('should disable verify button when code is incomplete', async () => {
      const user = userEvent.setup()
      render(<MFAChallenge />)

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      expect(verifyButton).toBeDisabled()

      // Type only 5 digits
      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      expect(verifyButton).toBeDisabled()
    })

    it('should show loading state during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      const verifyButton = screen.getByRole('button', { name: /verifying/i })

      await waitFor(() => {
        expect(verifyButton).toBeDisabled()
      })
    })

    it('should show success state after verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockResolvedValue(undefined)

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      await waitFor(() => {
        expect(screen.getByText(/verified/i)).toBeInTheDocument()
      })
    })

    it('should show error on invalid code', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid verification code'))

      render(<MFAChallenge onVerify={mockOnVerify} onError={mockOnError} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '0')
      await user.type(screen.getByLabelText('Digit 2'), '0')
      await user.type(screen.getByLabelText('Digit 3'), '0')
      await user.type(screen.getByLabelText('Digit 4'), '0')
      await user.type(screen.getByLabelText('Digit 5'), '0')
      await user.type(screen.getByLabelText('Digit 6'), '0')

      await waitFor(() => {
        expect(screen.getByText(/invalid verification code/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should clear digits on error', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '0')
      await user.type(screen.getByLabelText('Digit 2'), '0')
      await user.type(screen.getByLabelText('Digit 3'), '0')
      await user.type(screen.getByLabelText('Digit 4'), '0')
      await user.type(screen.getByLabelText('Digit 5'), '0')
      await user.type(screen.getByLabelText('Digit 6'), '0')

      await waitFor(() => {
        // All digit inputs should be cleared
        for (let i = 1; i <= 6; i++) {
          expect(screen.getByLabelText(`Digit ${i}`)).toHaveValue('')
        }
      })
    })

    it('should track failed attempts', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      // Three failed attempts
      for (let attempt = 0; attempt < 3; attempt++) {
        const digit1 = screen.getByLabelText('Digit 1')
        await user.type(digit1, '0')
        await user.type(screen.getByLabelText('Digit 2'), '0')
        await user.type(screen.getByLabelText('Digit 3'), '0')
        await user.type(screen.getByLabelText('Digit 4'), '0')
        await user.type(screen.getByLabelText('Digit 5'), '0')
        await user.type(screen.getByLabelText('Digit 6'), String(attempt + 1))

        await waitFor(() => {
          expect(screen.getByLabelText('Digit 1')).toHaveValue('')
        })
      }

      // After 3 failures, should show help message
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
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      mockOnRequestNewCode.mockResolvedValue(undefined)

      render(<MFAChallenge method="sms" allowResend={true} onRequestNewCode={mockOnRequestNewCode} />)

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/resend code in/i)).toBeInTheDocument()
      })
    })

    it('should disable resend button during cooldown', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      mockOnRequestNewCode.mockResolvedValue(undefined)

      render(<MFAChallenge method="sms" allowResend={true} onRequestNewCode={mockOnRequestNewCode} />)

      const resendButton = screen.getByRole('button', { name: /resend code/i })
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/resend code in/i)).toBeInTheDocument()
      })

      // Button with countdown text should be disabled
      const disabledButton = screen.getByText(/resend code in/i)
      expect(disabledButton).toBeDisabled()
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
    it('should disable digit inputs during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      await waitFor(() => {
        expect(screen.getByLabelText('Digit 1')).toBeDisabled()
      })
    })

    it('should show loading spinner during verification', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      await waitFor(() => {
        const spinner = document.querySelector('.animate-spin')
        expect(spinner).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper aria-labels on digit inputs', () => {
      render(<MFAChallenge />)

      for (let i = 1; i <= 6; i++) {
        expect(screen.getByLabelText(`Digit ${i}`)).toBeInTheDocument()
      }
    })

    it('should have error role on error message', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Invalid code'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '0')
      await user.type(screen.getByLabelText('Digit 2'), '0')
      await user.type(screen.getByLabelText('Digit 3'), '0')
      await user.type(screen.getByLabelText('Digit 4'), '0')
      await user.type(screen.getByLabelText('Digit 5'), '0')
      await user.type(screen.getByLabelText('Digit 6'), '0')

      await waitFor(() => {
        const errorContainer = screen.getByText(/invalid code/i).closest('div')
        expect(errorContainer).toHaveClass('bg-destructive/15')
      })
    })

    it('should have descriptive helper text', () => {
      render(<MFAChallenge />)

      expect(screen.getByText(/enter the 6-digit code/i)).toBeInTheDocument()
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

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      // Should not throw — shows success state
      await waitFor(() => {
        expect(screen.getByText(/verified/i)).toBeInTheDocument()
      })
    })

    it('should handle missing onError gracefully', async () => {
      const user = userEvent.setup()
      mockOnVerify.mockRejectedValue(new Error('Test error'))

      render(<MFAChallenge onVerify={mockOnVerify} />)

      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '0')
      await user.type(screen.getByLabelText('Digit 2'), '0')
      await user.type(screen.getByLabelText('Digit 3'), '0')
      await user.type(screen.getByLabelText('Digit 4'), '0')
      await user.type(screen.getByLabelText('Digit 5'), '0')
      await user.type(screen.getByLabelText('Digit 6'), '0')

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

      // First attempt - error
      const digit1 = screen.getByLabelText('Digit 1')
      await user.type(digit1, '0')
      await user.type(screen.getByLabelText('Digit 2'), '0')
      await user.type(screen.getByLabelText('Digit 3'), '0')
      await user.type(screen.getByLabelText('Digit 4'), '0')
      await user.type(screen.getByLabelText('Digit 5'), '0')
      await user.type(screen.getByLabelText('Digit 6'), '0')

      await waitFor(() => {
        expect(screen.getByText(/first error/i)).toBeInTheDocument()
      })

      // Second attempt - success (digits cleared on error, type again)
      await user.type(screen.getByLabelText('Digit 1'), '1')
      await user.type(screen.getByLabelText('Digit 2'), '2')
      await user.type(screen.getByLabelText('Digit 3'), '3')
      await user.type(screen.getByLabelText('Digit 4'), '4')
      await user.type(screen.getByLabelText('Digit 5'), '5')
      await user.type(screen.getByLabelText('Digit 6'), '6')

      await waitFor(() => {
        expect(screen.queryByText(/first error/i)).not.toBeInTheDocument()
      })
    })
  })
})
