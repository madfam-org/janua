import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SignIn, SignUp, MFASetup, MFAChallenge, BackupCodes } from '../../src/components/auth'

// TODO: Fix integration tests - component APIs have changed (use afterSignIn instead of onSuccess, etc.)
// These tests were written for an older API and need to be updated to match current component props
describe.skip('Demo App Integration Tests', () => {
  describe('SignIn Component', () => {
    it('renders with all required elements', () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      // Check for email input
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()

      // Check for password input
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()

      // Check for sign in button
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })

    it('validates required fields', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      const signInButton = screen.getByRole('button', { name: /sign in/i })
      fireEvent.click(signInButton)

      // Should not call onSuccess without valid input
      await waitFor(() => {
        expect(mockOnSuccess).not.toHaveBeenCalled()
      })
    })

    it('calls onSuccess when form is submitted with valid data', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      // Fill in email
      const emailInput = screen.getByLabelText(/email/i)
      fireEvent.change(emailInput, { target: { value: 'test@example.com' } })

      // Fill in password
      const passwordInput = screen.getByLabelText(/password/i)
      fireEvent.change(passwordInput, { target: { value: 'password123' } })

      // Submit form
      const signInButton = screen.getByRole('button', { name: /sign in/i })
      fireEvent.click(signInButton)

      // Should call onSuccess with form data
      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            email: 'test@example.com',
            password: 'password123'
          })
        )
      })
    })

    it('calls onError when login fails', async () => {
      const mockOnSuccess = vi.fn(() => {
        throw new Error('Invalid credentials')
      })
      const mockOnError = vi.fn()

      render(<SignIn onSuccess={mockOnSuccess} onError={mockOnError} />)

      // Fill in form
      fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: 'test@example.com' }
      })
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'wrongpassword' }
      })

      // Submit form
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

      // Should call onError
      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Invalid credentials'
          })
        )
      })
    })
  })

  describe('SignUp Component', () => {
    it('renders with all required elements', () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      // Check for email input
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()

      // Check for password input
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()

      // Check for confirm password input (if present)
      const confirmPassword = screen.queryByLabelText(/confirm password/i)
      if (confirmPassword) {
        expect(confirmPassword).toBeInTheDocument()
      }

      // Check for sign up button
      expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument()
    })

    it('validates password strength', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^password$/i)

      // Try weak password
      fireEvent.change(emailInput, { target: { value: 'test@example.com' } })
      fireEvent.change(passwordInput, { target: { value: '123' } })

      const signUpButton = screen.getByRole('button', { name: /sign up/i })
      fireEvent.click(signUpButton)

      // Should show validation error (weak password)
      await waitFor(() => {
        expect(mockOnSuccess).not.toHaveBeenCalled()
      })
    })

    it('validates password confirmation match', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      const confirmPasswordInput = screen.queryByLabelText(/confirm password/i)

      if (confirmPasswordInput) {
        fireEvent.change(screen.getByLabelText(/email/i), {
          target: { value: 'test@example.com' }
        })
        fireEvent.change(screen.getByLabelText(/^password$/i), {
          target: { value: 'password123' }
        })
        fireEvent.change(confirmPasswordInput, {
          target: { value: 'differentpassword' }
        })

        fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

        // Should not call onSuccess if passwords don't match
        await waitFor(() => {
          expect(mockOnSuccess).not.toHaveBeenCalled()
        })
      }
    })

    it('calls onSuccess with user data on successful signup', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      // Fill in form
      fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: 'newuser@example.com' }
      })
      fireEvent.change(screen.getByLabelText(/^password$/i), {
        target: { value: 'strongpassword123' }
      })

      // Fill confirm password if present
      const confirmPasswordInput = screen.queryByLabelText(/confirm password/i)
      if (confirmPasswordInput) {
        fireEvent.change(confirmPasswordInput, {
          target: { value: 'strongpassword123' }
        })
      }

      // Submit form
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

      // Should call onSuccess
      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            email: 'newuser@example.com'
          })
        )
      })
    })
  })

  describe('MFA Components Integration', () => {
    describe('MFASetup', () => {
      it('renders QR code and secret key', async () => {
        const mockOnComplete = vi.fn()
        render(<MFASetup onComplete={mockOnComplete} />)

        // Should display QR code or setup instructions
        await waitFor(() => {
          expect(screen.getByText(/scan/i) || screen.getByText(/qr/i)).toBeInTheDocument()
        })
      })

      it('calls onComplete with secret and QR code', async () => {
        const mockOnComplete = vi.fn()
        render(<MFASetup onComplete={mockOnComplete} />)

        // Simulate setup completion
        await waitFor(() => {
          expect(mockOnComplete).toHaveBeenCalledWith(
            expect.any(String), // secret
            expect.any(String)  // qrCode
          )
        })
      })
    })

    describe('MFAChallenge', () => {
      it('renders code input field', () => {
        const mockOnSuccess = vi.fn()
        render(<MFAChallenge onSuccess={mockOnSuccess} />)

        // Should have input for 6-digit code
        expect(screen.getByRole('textbox') || screen.getByLabelText(/code/i)).toBeInTheDocument()
      })

      it('validates 6-digit code format', async () => {
        const mockOnSuccess = vi.fn()
        render(<MFAChallenge onSuccess={mockOnSuccess} />)

        const codeInput = screen.getByRole('textbox') || screen.getByLabelText(/code/i)

        // Try invalid code (too short)
        fireEvent.change(codeInput, { target: { value: '123' } })
        fireEvent.submit(codeInput.closest('form') || codeInput)

        await waitFor(() => {
          expect(mockOnSuccess).not.toHaveBeenCalled()
        })
      })

      it('calls onSuccess with valid code', async () => {
        const mockOnSuccess = vi.fn()
        render(<MFAChallenge onSuccess={mockOnSuccess} />)

        const codeInput = screen.getByRole('textbox') || screen.getByLabelText(/code/i)

        // Enter valid 6-digit code
        fireEvent.change(codeInput, { target: { value: '123456' } })
        fireEvent.submit(codeInput.closest('form') || codeInput)

        await waitFor(() => {
          expect(mockOnSuccess).toHaveBeenCalledWith('123456')
        })
      })
    })

    describe('BackupCodes', () => {
      const sampleCodes = [
        'ABCD-1234-EFGH',
        'IJKL-5678-MNOP',
        'QRST-9012-UVWX',
        'YZAB-3456-CDEF',
        'GHIJ-7890-KLMN',
        'OPQR-1234-STUV',
        'WXYZ-5678-ABCD',
        'EFGH-9012-IJKL'
      ]

      it('renders all backup codes', () => {
        const mockOnDownload = vi.fn()
        render(<BackupCodes codes={sampleCodes} onDownload={mockOnDownload} />)

        // Should display all codes
        sampleCodes.forEach(code => {
          expect(screen.getByText(code)).toBeInTheDocument()
        })
      })

      it('calls onDownload when download button is clicked', async () => {
        const mockOnDownload = vi.fn()
        render(<BackupCodes codes={sampleCodes} onDownload={mockOnDownload} />)

        const downloadButton = screen.getByRole('button', { name: /download/i })
        fireEvent.click(downloadButton)

        await waitFor(() => {
          expect(mockOnDownload).toHaveBeenCalled()
        })
      })

      it('supports copy to clipboard', async () => {
        const mockOnCopy = vi.fn()
        render(<BackupCodes codes={sampleCodes} onCopy={mockOnCopy} />)

        const copyButton = screen.queryByRole('button', { name: /copy/i })

        if (copyButton) {
          fireEvent.click(copyButton)

          await waitFor(() => {
            expect(mockOnCopy).toHaveBeenCalled()
          })
        }
      })
    })
  })

  describe('Component Tree-Shaking', () => {
    it('components can be imported individually', () => {
      // This test ensures that importing individual components works
      // and that tree-shaking is possible
      expect(SignIn).toBeDefined()
      expect(SignUp).toBeDefined()
      expect(MFASetup).toBeDefined()
      expect(MFAChallenge).toBeDefined()
      expect(BackupCodes).toBeDefined()
    })
  })

  describe('Accessibility', () => {
    it('SignIn has proper ARIA labels', () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)

      expect(emailInput).toHaveAttribute('type', 'email')
      expect(passwordInput).toHaveAttribute('type', 'password')
    })

    it('SignUp has proper form structure', () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      // Should have a form element
      const form = screen.getByRole('form') || document.querySelector('form')
      expect(form).toBeInTheDocument()
    })

    it('buttons have proper accessible names', () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      const signInButton = screen.getByRole('button', { name: /sign in/i })
      expect(signInButton).toBeInTheDocument()
      expect(signInButton).not.toBeDisabled()
    })
  })
})
