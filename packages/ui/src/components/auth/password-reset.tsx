import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export interface PasswordResetProps {
  /** Optional custom class name */
  className?: string
  /** Current step in the password reset flow */
  step?: 'request' | 'verify' | 'reset' | 'success'
  /** Email address for password reset */
  email?: string
  /** Reset token from email link */
  token?: string
  /** Callback to request password reset */
  onRequestReset?: (email: string) => Promise<void>
  /** Callback to verify reset token */
  onVerifyToken?: (token: string) => Promise<void>
  /** Callback to reset password */
  onResetPassword?: (token: string, newPassword: string) => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Callback to navigate back to sign in */
  onBackToSignIn?: () => void
  /** Custom logo URL */
  logoUrl?: string
}

export function PasswordReset({
  className,
  step: initialStep = 'request',
  email: initialEmail = '',
  token: initialToken,
  onRequestReset,
  onVerifyToken,
  onResetPassword,
  onError,
  onBackToSignIn,
  logoUrl,
}: PasswordResetProps) {
  const [step, setStep] = React.useState(initialStep)
  const [email, setEmail] = React.useState(initialEmail)
  const [token, setToken] = React.useState(initialToken || '')
  const [newPassword, setNewPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Auto-verify token if provided
  React.useEffect(() => {
    if (initialToken && onVerifyToken && step === 'request') {
      setStep('verify')
      setIsLoading(true)
      onVerifyToken(initialToken)
        .then(() => {
          setStep('reset')
        })
        .catch((err) => {
          const error = err instanceof Error ? err : new Error('Invalid or expired reset link')
          setError(error.message)
          onError?.(error)
          setStep('request')
        })
        .finally(() => setIsLoading(false))
    }
  }, [initialToken, onVerifyToken, onError])

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onRequestReset) return

    setIsLoading(true)
    setError(null)

    try {
      await onRequestReset(email)
      setStep('verify')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to send reset email')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onResetPassword) return

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await onResetPassword(token, newPassword)
      setStep('success')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to reset password')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const getPasswordStrength = (password: string): { strength: number; label: string; color: string } => {
    let strength = 0
    if (password.length >= 8) strength += 25
    if (password.length >= 12) strength += 25
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 25
    if (/\d/.test(password)) strength += 15
    if (/[^a-zA-Z0-9]/.test(password)) strength += 10

    if (strength >= 75) return { strength, label: 'Strong', color: 'bg-green-500' }
    if (strength >= 50) return { strength, label: 'Medium', color: 'bg-yellow-500' }
    return { strength, label: 'Weak', color: 'bg-red-500' }
  }

  const passwordStrength = getPasswordStrength(newPassword)

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-8" />
        </div>
      )}

      {/* Request Reset Step */}
      {step === 'request' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-primary/10 p-3">
                <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Reset your password</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Enter your email address and we'll send you a link to reset your password
            </p>
          </div>

          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleRequestReset} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
                autoFocus
              />
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Sending...
                </>
              ) : (
                'Send reset link'
              )}
            </Button>

            {onBackToSignIn && (
              <div className="text-center">
                <button
                  type="button"
                  className="text-sm text-primary hover:underline"
                  onClick={onBackToSignIn}
                >
                  ← Back to sign in
                </button>
              </div>
            )}
          </form>
        </>
      )}

      {/* Verify Step (Email Sent) */}
      {step === 'verify' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-green-100 p-3">
                <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                  <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Check your email</h2>
            <p className="text-sm text-muted-foreground mt-2">
              We've sent a password reset link to
              <br />
              <span className="font-medium text-foreground">{email}</span>
            </p>
          </div>

          <div className="space-y-4">
            <div className="bg-muted rounded-lg p-4">
              <h4 className="text-sm font-medium mb-2">Didn't receive the email?</h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• Check your spam or junk folder</li>
                <li>• Make sure you entered the correct email address</li>
                <li>• Wait a few minutes for the email to arrive</li>
              </ul>
            </div>

            <Button
              variant="outline"
              className="w-full"
              onClick={() => setStep('request')}
            >
              Try a different email
            </Button>

            {onBackToSignIn && (
              <div className="text-center">
                <button
                  type="button"
                  className="text-sm text-primary hover:underline"
                  onClick={onBackToSignIn}
                >
                  ← Back to sign in
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* Reset Password Step */}
      {step === 'reset' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-primary/10 p-3">
                <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Create new password</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Your new password must be different from previously used passwords
            </p>
          </div>

          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleResetPassword} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={isLoading}
                minLength={8}
                autoFocus
              />
              {newPassword && (
                <>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={cn('h-full transition-all', passwordStrength.color)}
                        style={{ width: `${passwordStrength.strength}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium">{passwordStrength.label}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Use 8+ characters with uppercase, lowercase, numbers, and symbols
                  </p>
                </>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={isLoading}
                minLength={8}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Resetting...
                </>
              ) : (
                'Reset password'
              )}
            </Button>
          </form>
        </>
      )}

      {/* Success Step */}
      {step === 'success' && (
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
            <h2 className="text-2xl font-bold">Password reset successful</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Your password has been successfully reset. You can now sign in with your new password.
            </p>
          </div>

          {onBackToSignIn && (
            <Button className="w-full" onClick={onBackToSignIn}>
              Continue to sign in
            </Button>
          )}
        </>
      )}
    </Card>
  )
}
