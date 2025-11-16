import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export interface MFAChallengeProps {
  /** Optional custom class name */
  className?: string
  /** User identifier for display */
  userEmail?: string
  /** Callback when code is verified */
  onVerify?: (code: string) => Promise<void>
  /** Callback to use backup code instead */
  onUseBackupCode?: () => void
  /** Callback to request new code (SMS) */
  onRequestNewCode?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** MFA method type */
  method?: 'totp' | 'sms'
  /** Show use backup code option */
  showBackupCodeOption?: boolean
  /** Allow resending code (for SMS) */
  allowResend?: boolean
}

export function MFAChallenge({
  className,
  userEmail,
  onVerify,
  onUseBackupCode,
  onRequestNewCode,
  onError,
  method = 'totp',
  showBackupCodeOption = true,
  allowResend = false,
}: MFAChallengeProps) {
  const [code, setCode] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = React.useState(0)
  const [attempts, setAttempts] = React.useState(0)

  // Cooldown timer for resend
  React.useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [resendCooldown])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      await onVerify?.(code)
      // Success - parent component handles redirect
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Invalid verification code')
      setError(error.message)
      onError?.(error)
      setAttempts((prev) => prev + 1)
      setCode('') // Clear code on error
    } finally {
      setIsLoading(false)
    }
  }

  const handleResend = async () => {
    if (resendCooldown > 0) return

    setIsLoading(true)
    setError(null)

    try {
      await onRequestNewCode?.()
      setResendCooldown(60) // 60 second cooldown
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to resend code')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  // Auto-submit when 6 digits entered
  React.useEffect(() => {
    if (code.length === 6 && !isLoading) {
      handleSubmit(new Event('submit') as any)
    }
  }, [code])

  const methodText = method === 'sms' ? 'your phone' : 'your authenticator app'

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Header */}
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
        <h2 className="text-2xl font-bold">Two-factor authentication</h2>
        <p className="text-sm text-muted-foreground mt-2">
          {userEmail && (
            <>
              Signing in as <span className="font-medium">{userEmail}</span>
              <br />
            </>
          )}
          Enter the code from {methodText}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Error Message */}
        {error && (
          <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
            {error}
            {attempts >= 3 && (
              <p className="mt-2">
                Having trouble? Try using a backup code or contact support.
              </p>
            )}
          </div>
        )}

        {/* Code Input */}
        <div className="space-y-2">
          <Label htmlFor="mfaCode">Verification code</Label>
          <Input
            id="mfaCode"
            type="text"
            inputMode="numeric"
            pattern="[0-9]{6}"
            placeholder="000000"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            maxLength={6}
            required
            disabled={isLoading}
            autoFocus
            autoComplete="one-time-code"
            className="text-center text-2xl tracking-widest"
          />
          <p className="text-xs text-muted-foreground text-center">
            Enter the 6-digit code
          </p>
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          className="w-full"
          disabled={isLoading || code.length !== 6}
        >
          {isLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Verifying...
            </>
          ) : (
            'Verify'
          )}
        </Button>

        {/* Resend Code (SMS only) */}
        {method === 'sms' && allowResend && (
          <div className="text-center">
            <button
              type="button"
              className="text-sm text-primary hover:underline disabled:opacity-50 disabled:no-underline"
              onClick={handleResend}
              disabled={resendCooldown > 0 || isLoading}
            >
              {resendCooldown > 0
                ? `Resend code in ${resendCooldown}s`
                : 'Resend code'}
            </button>
          </div>
        )}

        {/* Use Backup Code */}
        {showBackupCodeOption && onUseBackupCode && (
          <>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  Or
                </span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={onUseBackupCode}
            >
              Use a backup code
            </Button>
          </>
        )}
      </form>

      {/* Help Text */}
      <div className="mt-6 p-4 bg-muted rounded-lg">
        <h4 className="text-sm font-medium mb-2">Need help?</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• Make sure your authenticator app is synced with the correct time</li>
          <li>• The code expires after 30 seconds - try generating a new one</li>
          <li>• Lost access to your authenticator? Use a backup code</li>
        </ul>
      </div>
    </Card>
  )
}
