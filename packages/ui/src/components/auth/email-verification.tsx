import * as React from 'react'
import { Button } from '../button'
import { Card } from '../card'
import { cn } from '../../lib/utils'
import { parseApiError, formatErrorMessage, getBriefErrorMessage } from '../../lib/error-messages'

export interface EmailVerificationProps {
  /** Optional custom class name */
  className?: string
  /** Email address being verified */
  email: string
  /** Current verification status */
  status?: 'pending' | 'verifying' | 'success' | 'error'
  /** Verification token from email link */
  token?: string
  /** Callback to verify email */
  onVerify?: (token: string) => Promise<void>
  /** Callback to resend verification email */
  onResendEmail?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Callback when verification is complete */
  onComplete?: () => void
  /** Show resend option */
  showResend?: boolean
  /** Custom logo URL */
  logoUrl?: string
  /** Plinto client instance for API integration */
  plintoClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
}

export function EmailVerification({
  className,
  email,
  status: initialStatus = 'pending',
  token: initialToken,
  onVerify,
  onResendEmail,
  onError,
  onComplete,
  showResend = true,
  logoUrl,
  plintoClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: EmailVerificationProps) {
  const [status, setStatus] = React.useState(initialStatus)
  const [error, setError] = React.useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = React.useState(0)

  // Auto-verify if token is provided
  React.useEffect(() => {
    if (initialToken && status === 'pending') {
      setStatus('verifying')

      const verify = async () => {
        if (plintoClient) {
          // Use Plinto SDK for email verification
          await plintoClient.auth.verifyEmail(initialToken)
        } else if (onVerify) {
          // Use custom callback if provided
          await onVerify(initialToken)
        } else {
          // Fallback to direct fetch
          const response = await fetch(`${apiUrl}/api/v1/auth/email/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ token: initialToken }),
          })

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}))
            const actionableError = parseApiError(errorData, { 
              status: response.status,
              code: errorData.code
            })
            throw new Error(actionableError.message)
          }
        }
      }

      verify()
        .then(() => {
          setStatus('success')
          onComplete?.()
        })
        .catch((err) => {
          const actionableError = parseApiError(err, {
            message: err instanceof Error ? err.message : 'Invalid or expired verification link'
          })
          setError(getBriefErrorMessage(actionableError))
          onError?.(new Error(actionableError.message))
          setStatus('error')
        })
    }
  }, [initialToken, plintoClient, onVerify, onError, onComplete, apiUrl, status])

  // Cooldown timer for resend
  React.useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [resendCooldown])

  const handleResend = async () => {
    if (resendCooldown > 0) return

    setError(null)

    try {
      if (plintoClient) {
        // Use Plinto SDK to resend verification email
        await plintoClient.auth.resendVerificationEmail({ email })
        setResendCooldown(60) // 60 second cooldown
      } else if (onResendEmail) {
        // Use custom callback if provided
        await onResendEmail()
        setResendCooldown(60)
      } else {
        // Fallback to direct fetch
        const response = await fetch(`${apiUrl}/api/v1/auth/email/resend`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          const actionableError = parseApiError(errorData, { 
            status: response.status 
          })
          throw new Error(actionableError.message)
        }

        setResendCooldown(60)
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: err instanceof Error ? err.message : 'Failed to resend verification email'
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
    }
  }

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-8" />
        </div>
      )}

      {/* Pending State */}
      {status === 'pending' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-blue-100 p-3">
                <svg className="w-8 h-8 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                  <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Verify your email</h2>
            <p className="text-sm text-muted-foreground mt-2">
              We've sent a verification email to
              <br />
              <span className="font-medium text-foreground">{email}</span>
            </p>
          </div>

          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div className="bg-muted rounded-lg p-4">
              <h4 className="text-sm font-medium mb-2">Check your inbox</h4>
              <p className="text-xs text-muted-foreground">
                Click the verification link in the email to verify your account. The link will expire in 24 hours.
              </p>
            </div>

            {showResend && onResendEmail && (
              <div className="text-center">
                <p className="text-sm text-muted-foreground mb-2">
                  Didn't receive the email?
                </p>
                <button
                  onClick={handleResend}
                  disabled={resendCooldown > 0}
                  className="text-sm text-primary hover:underline disabled:opacity-50 disabled:no-underline"
                >
                  {resendCooldown > 0
                    ? `Resend in ${resendCooldown}s`
                    : 'Resend verification email'}
                </button>
              </div>
            )}

            <div className="bg-muted rounded-lg p-4">
              <h4 className="text-sm font-medium mb-2">Didn't receive the email?</h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• Check your spam or junk folder</li>
                <li>• Make sure you entered the correct email address</li>
                <li>• Wait a few minutes for the email to arrive</li>
              </ul>
            </div>
          </div>
        </>
      )}

      {/* Verifying State */}
      {status === 'verifying' && (
        <>
          <div className="text-center py-12">
            <div className="flex justify-center mb-4">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
            <h2 className="text-2xl font-bold">Verifying your email</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Please wait while we verify your email address...
            </p>
          </div>
        </>
      )}

      {/* Success State */}
      {status === 'success' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-green-100 p-3">
                <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Email verified!</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Your email address <span className="font-medium text-foreground">{email}</span> has been successfully verified.
            </p>
          </div>

          {onComplete && (
            <Button className="w-full" onClick={onComplete}>
              Continue
            </Button>
          )}
        </>
      )}

      {/* Error State */}
      {status === 'error' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-red-100 p-3">
                <svg className="w-8 h-8 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Verification failed</h2>
            <p className="text-sm text-muted-foreground mt-2">
              {error || 'The verification link is invalid or has expired.'}
            </p>
          </div>

          {showResend && onResendEmail && (
            <div className="space-y-4">
              <Button
                variant="outline"
                className="w-full"
                onClick={handleResend}
                disabled={resendCooldown > 0}
              >
                {resendCooldown > 0
                  ? `Resend in ${resendCooldown}s`
                  : 'Resend verification email'}
              </Button>

              <div className="bg-muted rounded-lg p-4">
                <h4 className="text-sm font-medium mb-2">Common issues</h4>
                <ul className="text-xs text-muted-foreground space-y-1">
                  <li>• The verification link may have expired (valid for 24 hours)</li>
                  <li>• The link may have already been used</li>
                  <li>• Try requesting a new verification email</li>
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
