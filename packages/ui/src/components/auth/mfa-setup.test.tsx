import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { MFASetup } from './mfa-setup'

describe('MFASetup', () => {
  const mockMFAData = {
    secret: 'JBSWY3DPEHPK3PXP',
    qrCode: 'data:image/png;base64,iVBORw0KGgo...',
    backupCodes: ['CODE1234', 'CODE5678', 'CODE9012'],
  }

  const mockOnFetchSetupData = vi.fn()
  const mockOnComplete = vi.fn()
  const mockOnError = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    global.alert = vi.fn()
    delete (window as any).location
    window.location = { href: '' } as any

    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })

    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
  })

  describe('Rendering', () => {
    it('should render setup wizard with provided MFA data', () => {
      render(<MFASetup mfaData={mockMFAData} />)

      expect(screen.getByText(/set up two-factor authentication/i)).toBeInTheDocument()
      expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument()
    })

    it('should show loading state when fetching MFA data', () => {
      mockOnFetchSetupData.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockMFAData), 100))
      )

      render(<MFASetup onFetchSetupData={mockOnFetchSetupData} />)

      expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
    })

    it('should fetch MFA data on mount when not provided', async () => {
      mockOnFetchSetupData.mockResolvedValue(mockMFAData)

      render(<MFASetup onFetchSetupData={mockOnFetchSetupData} />)

      await waitFor(() => {
        expect(mockOnFetchSetupData).toHaveBeenCalled()
      })
    })

    it('should show error when fetch fails', async () => {
      mockOnFetchSetupData.mockRejectedValue(new Error('Failed to fetch'))

      render(<MFASetup onFetchSetupData={mockOnFetchSetupData} onError={mockOnError} />)

      await waitFor(() => {
        expect(screen.getByText(/failed to load mfa setup data/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })
  })

  describe('Step 1: Scan QR Code', () => {
    it('should display QR code', () => {
      render(<MFASetup mfaData={mockMFAData} />)

      const qrImage = screen.getByAltText(/qr code/i)
      expect(qrImage).toBeInTheDocument()
      expect(qrImage).toHaveAttribute('src', mockMFAData.qrCode)
    })

    it('should display manual entry secret', () => {
      render(<MFASetup mfaData={mockMFAData} />)

      expect(screen.getByText(mockMFAData.secret)).toBeInTheDocument()
      expect(screen.getByText(/or enter this code manually/i)).toBeInTheDocument()
    })

    it('should copy secret to clipboard', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const copyButton = screen.getByRole('button', { name: /copy/i })
      await user.click(copyButton)

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockMFAData.secret)
      expect(screen.getByText(/copied/i)).toBeInTheDocument()
    })

    it('should show copied state temporarily', async () => {
      const user = userEvent.setup()
      vi.useFakeTimers()

      render(<MFASetup mfaData={mockMFAData} />)

      const copyButton = screen.getByRole('button', { name: /copy/i })
      await user.click(copyButton)

      expect(screen.getByText(/copied/i)).toBeInTheDocument()

      vi.advanceTimersByTime(2000)

      await waitFor(() => {
        expect(screen.queryByText(/copied/i)).not.toBeInTheDocument()
      })

      vi.useRealTimers()
    })

    it('should navigate to verify step', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument()
      expect(screen.getByText(/verify your code/i)).toBeInTheDocument()
    })

    it('should call onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} onCancel={mockOnCancel} />)

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      expect(mockOnCancel).toHaveBeenCalled()
    })

    it('should not show cancel button when callback not provided', () => {
      render(<MFASetup mfaData={mockMFAData} />)

      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument()
    })
  })

  describe('Step 2: Verify Code', () => {
    it('should display verification code input', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
    })

    it('should only accept numeric input', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, 'abc123def')

      expect(codeInput).toHaveValue('123')
    })

    it('should limit input to 6 digits', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '1234567890')

      expect(codeInput).toHaveValue('123456')
    })

    it('should verify code and proceed to backup codes', async () => {
      const user = userEvent.setup()
      mockOnComplete.mockResolvedValue(undefined)

      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} showBackupCodes={true} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalledWith('123456')
        expect(screen.getByText(/step 3 of 3/i)).toBeInTheDocument()
      })
    })

    it('should skip backup codes step when disabled', async () => {
      const user = userEvent.setup()
      mockOnComplete.mockResolvedValue(undefined)

      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} showBackupCodes={false} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalledWith('123456')
        expect(screen.queryByText(/step 3 of 3/i)).not.toBeInTheDocument()
      })
    })

    it('should show error on invalid verification code', async () => {
      const user = userEvent.setup()
      mockOnComplete.mockRejectedValue(new Error('Invalid code'))

      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} onError={mockOnError} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(screen.getByText(/invalid code/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should disable verify button when code is incomplete', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

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
      mockOnComplete.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      expect(verifyButton).toHaveTextContent(/verifying/i)
      expect(verifyButton).toBeDisabled()
    })

    it('should allow going back to scan step', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const backButton = screen.getByRole('button', { name: /back/i })
      await user.click(backButton)

      expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument()
      expect(screen.getByText(/scan this qr code/i)).toBeInTheDocument()
    })
  })

  describe('Step 3: Backup Codes', () => {
    beforeEach(async () => {
      // Helper to navigate to backup codes step
      mockOnComplete.mockResolvedValue(undefined)
    })

    const navigateToBackupCodesStep = async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} showBackupCodes={true} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '123456')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(screen.getByText(/step 3 of 3/i)).toBeInTheDocument()
      })
    }

    it('should display backup codes', async () => {
      await navigateToBackupCodesStep()

      mockMFAData.backupCodes.forEach((code) => {
        expect(screen.getByText(code)).toBeInTheDocument()
      })
    })

    it('should download backup codes', async () => {
      await navigateToBackupCodesStep()

      const downloadButton = screen.getByRole('button', { name: /download codes/i })

      // Mock document methods
      const mockClick = vi.fn()
      const mockAppendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(() => null as any)
      const mockRemoveChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => null as any)
      const mockCreateElement = vi.spyOn(document, 'createElement').mockReturnValue({
        click: mockClick,
        href: '',
        download: '',
      } as any)

      const user = userEvent.setup()
      await user.click(downloadButton)

      expect(mockCreateElement).toHaveBeenCalledWith('a')
      expect(mockClick).toHaveBeenCalled()

      mockCreateElement.mockRestore()
      mockAppendChild.mockRestore()
      mockRemoveChild.mockRestore()
    })

    it('should show warning about backup codes', async () => {
      await navigateToBackupCodesStep()

      expect(screen.getByText(/important/i)).toBeInTheDocument()
      expect(screen.getByText(/each backup code can only be used once/i)).toBeInTheDocument()
    })

    it('should require download before completing', async () => {
      await navigateToBackupCodesStep()

      const completeButton = screen.getByRole('button', { name: /complete setup/i })

      const user = userEvent.setup()
      await user.click(completeButton)

      expect(global.alert).toHaveBeenCalledWith(
        'Please download your backup codes before continuing'
      )
    })

    it('should complete setup after download', async () => {
      await navigateToBackupCodesStep()

      const downloadButton = screen.getByRole('button', { name: /download codes/i })
      const completeButton = screen.getByRole('button', { name: /complete setup/i })

      // Mock document methods
      const mockClick = vi.fn()
      const mockAppendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(() => null as any)
      const mockRemoveChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => null as any)
      const mockCreateElement = vi.spyOn(document, 'createElement').mockReturnValue({
        click: mockClick,
        href: '',
        download: '',
      } as any)

      const user = userEvent.setup()
      await user.click(downloadButton)
      await user.click(completeButton)

      expect(window.location.href).toBe('/dashboard')

      mockCreateElement.mockRestore()
      mockAppendChild.mockRestore()
      mockRemoveChild.mockRestore()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
    })

    it('should have autocomplete attribute for OTP', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('autocomplete', 'one-time-code')
    })

    it('should have proper input mode for numeric entry', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      expect(codeInput).toHaveAttribute('inputmode', 'numeric')
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<MFASetup mfaData={mockMFAData} onCancel={mockOnCancel} />)

      await user.tab()
      expect(screen.getByRole('button', { name: /cancel/i })).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button', { name: /continue/i })).toHaveFocus()
    })
  })

  describe('Error Handling', () => {
    it('should handle clipboard write errors gracefully', async () => {
      const user = userEvent.setup()
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockRejectedValue(new Error('Clipboard error')),
        },
      })

      render(<MFASetup mfaData={mockMFAData} />)

      const copyButton = screen.getByRole('button', { name: /copy/i })
      await user.click(copyButton)

      expect(consoleError).toHaveBeenCalled()
      consoleError.mockRestore()
    })

    it('should display error from onError callback', async () => {
      const user = userEvent.setup()
      const error = new Error('Custom error')
      mockOnComplete.mockRejectedValue(error)

      render(<MFASetup mfaData={mockMFAData} onComplete={mockOnComplete} onError={mockOnError} />)

      const continueButton = screen.getByRole('button', { name: /continue/i })
      await user.click(continueButton)

      const codeInput = screen.getByLabelText(/verification code/i)
      await user.type(codeInput, '000000')

      const verifyButton = screen.getByRole('button', { name: /verify/i })
      await user.click(verifyButton)

      await waitFor(() => {
        expect(screen.getByText(/custom error/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalledWith(error)
      })
    })
  })
})
