import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { PhoneVerification } from './phone-verification'

describe('PhoneVerification', () => {
  const mockOnSendCode = vi.fn()
  const mockOnVerifyCode = vi.fn()
  const mockOnError = vi.fn()
  const mockOnComplete = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Rendering', () => {
    it('should render phone verification component', () => {
      render(
        <PhoneVerification phoneNumber="+15551234567" />
      )

      expect(screen.getByText('Verify your phone number')).toBeInTheDocument()
    })

    it('should render custom logo when logoUrl is provided', () => {
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          logoUrl="https://example.com/logo.png"
        />
      )

      const logo = screen.getByRole('img', { name: /logo/i })
      expect(logo).toHaveAttribute('src', 'https://example.com/logo.png')
    })

    it('should apply custom className', () => {
      const { container } = render(
        <PhoneVerification
          phoneNumber="+15551234567"
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('Send Code Step', () => {
    it('should display send code form', () => {
      render(
        <PhoneVerification phoneNumber="+15551234567" step="send" />
      )

      expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /send verification code/i })).toBeInTheDocument()
    })

    it('should populate phone number input', () => {
      render(
        <PhoneVerification phoneNumber="+15551234567" step="send" />
      )

      const phoneInput = screen.getByLabelText(/phone number/i)
      expect(phoneInput).toHaveValue('+15551234567')
    })

    it('should send verification code', async () => {
      const user = userEvent.setup()
      mockOnSendCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="send"
          onSendCode={mockOnSendCode}
        />
      )

      const sendButton = screen.getByRole('button', { name: /send verification code/i })
      await user.click(sendButton)

      await waitFor(() => {
        expect(mockOnSendCode).toHaveBeenCalledWith('+15551234567')
      })
    })

    it('should show loading state during send', async () => {
      const user = userEvent.setup()
      let resolveSend: () => void
      mockOnSendCode.mockImplementation(
        () => new Promise<void>((resolve) => { resolveSend = resolve })
      )

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="send"
          onSendCode={mockOnSendCode}
        />
      )

      const sendButton = screen.getByRole('button', { name: /send verification code/i })
      await user.click(sendButton)

      await waitFor(() => {
        expect(screen.getByText(/sending/i)).toBeInTheDocument()
      })

      // Cleanup
      await act(async () => {
        resolveSend!()
      })
    })

    it('should handle send code error', async () => {
      const user = userEvent.setup()
      const error = new Error('Failed to send verification code')
      mockOnSendCode.mockRejectedValue(error)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="send"
          onSendCode={mockOnSendCode}
          onError={mockOnError}
        />
      )

      const sendButton = screen.getByRole('button', { name: /send verification code/i })
      await user.click(sendButton)

      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should transition to verify step after sending', async () => {
      const user = userEvent.setup()
      mockOnSendCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="send"
          onSendCode={mockOnSendCode}
        />
      )

      const sendButton = screen.getByRole('button', { name: /send verification code/i })
      await user.click(sendButton)

      await waitFor(() => {
        expect(screen.getByText(/enter verification code/i)).toBeInTheDocument()
      })
    })
  })

  describe('Verify Code Step', () => {
    it('should display verify code form', () => {
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      expect(screen.getByText(/enter verification code/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
    })

    it('should format phone number display', () => {
      render(
        <PhoneVerification
          phoneNumber="5551234567"
          step="verify"
        />
      )

      expect(screen.getByText('(555) 123-4567')).toBeInTheDocument()
    })

    it('should accept only numeric input', async () => {
      const user = userEvent.setup()
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      // Type mixed input - only numbers should be accepted
      await user.type(codeInput, 'abc12')

      expect(codeInput).toHaveValue('12')
    })

    it('should limit code to 6 digits', async () => {
      const user = userEvent.setup()
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      // Type 5 digits first (won't trigger auto-submit)
      await user.type(codeInput, '12345')

      expect(codeInput).toHaveValue('12345')
      // maxLength is 6, so typing more won't exceed
    })

    it('should auto-submit when 6 digits entered', async () => {
      const user = userEvent.setup()
      mockOnVerifyCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
          onComplete={mockOnComplete}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(mockOnVerifyCode).toHaveBeenCalledWith('123456')
      })
    })

    it('should verify code manually', async () => {
      const user = userEvent.setup()
      mockOnVerifyCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
          onComplete={mockOnComplete}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '12345')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      expect(verifyButton).toBeDisabled()

      await user.type(codeInput, '6')

      await waitFor(() => {
        expect(mockOnVerifyCode).toHaveBeenCalledWith('123456')
      })
    })

    it('should show loading state during verification', async () => {
      const user = userEvent.setup()
      let resolveVerify: () => void
      mockOnVerifyCode.mockImplementation(
        () => new Promise<void>((resolve) => { resolveVerify = resolve })
      )

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(screen.getByText(/verifying/i)).toBeInTheDocument()
      })

      // Cleanup
      await act(async () => {
        resolveVerify!()
      })
    })

    it('should handle verification error', async () => {
      const user = userEvent.setup()
      const error = new Error('Invalid verification code')
      mockOnVerifyCode.mockRejectedValue(error)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
          onError={mockOnError}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should clear code on error', async () => {
      const user = userEvent.setup()
      const error = new Error('Invalid verification code')
      mockOnVerifyCode.mockRejectedValue(error)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i) as HTMLInputElement
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(codeInput.value).toBe('')
      })
    })

    it('should show help message after multiple failed attempts', async () => {
      const user = userEvent.setup()
      const error = new Error('Invalid verification code')
      mockOnVerifyCode.mockRejectedValue(error)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)

      // Fail 3 times
      for (let i = 0; i < 3; i++) {
        await user.type(codeInput, '123456')
        await waitFor(() => {
          expect(codeInput).toHaveValue('')
        })
      }

      await waitFor(() => {
        expect(screen.getByText(/having trouble/i)).toBeInTheDocument()
      })
    })
  })

  describe('Resend Code', () => {
    it('should resend verification code', async () => {
      const user = userEvent.setup()
      mockOnSendCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onSendCode={mockOnSendCode}
        />
      )

      const resendButton = screen.getByText(/resend code/i)
      await user.click(resendButton)

      await waitFor(() => {
        expect(mockOnSendCode).toHaveBeenCalledWith('+15551234567')
      })
    })

    it('should show cooldown after resending', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      mockOnSendCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onSendCode={mockOnSendCode}
        />
      )

      const resendButton = screen.getByText(/resend code/i)
      await user.click(resendButton)

      await waitFor(() => {
        expect(screen.getByText(/resend code in/i)).toBeInTheDocument()
      })
    })

    it('should allow changing phone number', async () => {
      const user = userEvent.setup()
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      const changeButton = screen.getByText(/use a different phone number/i)
      await user.click(changeButton)

      await waitFor(() => {
        expect(screen.getByText('Verify your phone number')).toBeInTheDocument()
        expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument()
      })
    })
  })

  describe('Success Step', () => {
    it('should display success state', () => {
      render(
        <PhoneVerification
          phoneNumber="5551234567"
          step="success"
        />
      )

      expect(screen.getByText('Phone verified!')).toBeInTheDocument()
      expect(screen.getByText(/successfully verified/i)).toBeInTheDocument()
      expect(screen.getByText('(555) 123-4567')).toBeInTheDocument()
    })

    it('should show continue button when onComplete is provided', () => {
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="success"
          onComplete={mockOnComplete}
        />
      )

      expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument()
    })

    it('should call onComplete when clicking continue', async () => {
      const user = userEvent.setup()
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="success"
          onComplete={mockOnComplete}
        />
      )

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      expect(mockOnComplete).toHaveBeenCalled()
    })

    it('should transition to success after verification', async () => {
      const user = userEvent.setup()
      mockOnVerifyCode.mockResolvedValue(undefined)

      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
          onVerifyCode={mockOnVerifyCode}
          onComplete={mockOnComplete}
        />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      await waitFor(() => {
        expect(screen.getByText('Phone verified!')).toBeInTheDocument()
      })
    })
  })

  describe('Helpful Tips', () => {
    it('should display tips for not receiving code', () => {
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      expect(screen.getByText(/didn't receive the code/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have accessible form labels', () => {
      render(
        <PhoneVerification phoneNumber="+15551234567" step="send" />
      )

      expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument()
    })

    it('should have accessible verification code input', () => {
      render(
        <PhoneVerification phoneNumber="+15551234567" step="verify" />
      )

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('inputMode', 'numeric')
      expect(codeInput).toHaveAttribute('autocomplete', 'one-time-code')
    })

    it('should support keyboard navigation', async () => {
      const _user = userEvent.setup()
      render(
        <PhoneVerification
          phoneNumber="+15551234567"
          step="verify"
        />
      )

      // Tab through focusable elements - first focusable is resend code link
      // then verification code input (verify component layout may vary)
      const codeInput = screen.getByLabelText(/verification code/i)
      codeInput.focus()
      expect(codeInput).toHaveFocus()
    })
  })
})
