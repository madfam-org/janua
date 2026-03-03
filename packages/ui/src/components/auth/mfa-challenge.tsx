import * as React from 'react'
import { Lock, Loader2, CheckCircle2 } from 'lucide-react'
import { Button } from '../button'
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
  const [digits, setDigits] = React.useState<string[]>(['', '', '', '', '', ''])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = React.useState(0)
  const [attempts, setAttempts] = React.useState(0)
  const [verified, setVerified] = React.useState(false)
  const inputRefs = React.useRef<(HTMLInputElement | null)[]>([])

  // Cooldown timer for resend
  React.useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [resendCooldown])

  const code = digits.join('')

  const handleVerify = React.useCallback(async (fullCode: string) => {
    if (fullCode.length !== 6 || isLoading) return
    setError(null)
    setIsLoading(true)

    try {
      await onVerify?.(fullCode)
      setVerified(true)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Invalid verification code')
      setError(error.message)
      onError?.(error)
      setAttempts((prev) => prev + 1)
      // Clear all digits on error
      setDigits(['', '', '', '', '', ''])
      inputRefs.current[0]?.focus()
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, onVerify, onError])

  const handleDigitChange = (index: number, value: string) => {
    // Only accept digits
    const digit = value.replace(/\D/g, '').slice(-1)
    const newDigits = [...digits]
    newDigits[index] = digit
    setDigits(newDigits)

    // Auto-advance to next input
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all 6 digits entered
    const fullCode = newDigits.join('')
    if (fullCode.length === 6) {
      handleVerify(fullCode)
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      // Move back on backspace when current input is empty
      const newDigits = [...digits]
      newDigits[index - 1] = ''
      setDigits(newDigits)
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (!pasted) return
    const newDigits = [...digits]
    for (let i = 0; i < 6; i++) {
      newDigits[i] = pasted[i] || ''
    }
    setDigits(newDigits)
    if (pasted.length === 6) {
      handleVerify(pasted)
    } else {
      inputRefs.current[Math.min(pasted.length, 5)]?.focus()
    }
  }

  const handleResend = async () => {
    if (resendCooldown > 0) return
    setIsLoading(true)
    setError(null)

    try {
      await onRequestNewCode?.()
      setResendCooldown(60)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to resend code')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await handleVerify(code)
  }

  const methodText = method === 'sms' ? 'your phone' : 'your authenticator app'

  // Success state
  if (verified) {
    return (
      <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
        <div className="text-center py-8" style={{ animation: 'janua-fade-in 300ms ease' }}>
          <div className="flex justify-center mb-4">
            <CheckCircle2 className="w-16 h-16 text-green-500" />
          </div>
          <h2 className="text-2xl font-bold">Verified</h2>
          <p className="text-sm text-muted-foreground mt-1">Redirecting...</p>
        </div>
      </Card>
    )
  }

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Header */}
      <div className="text-center mb-6" style={{ animation: 'janua-fade-in 300ms ease' }}>
        <div className="flex justify-center mb-4">
          <div className="rounded-full bg-primary/10 p-3">
            <Lock className="w-8 h-8 text-primary" />
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
          <div
            className="bg-destructive/15 text-destructive text-sm p-3 rounded-md"
            style={{ animation: 'janua-slide-up 200ms ease, janua-shake 400ms ease' }}
          >
            {error}
            {attempts >= 3 && (
              <p className="mt-2">
                Having trouble? Try using a backup code or contact support.
              </p>
            )}
          </div>
        )}

        {/* PIN-style digit inputs */}
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground text-center">
            Enter the 6-digit code
          </p>
          <div className="flex justify-center gap-2" onPaste={handlePaste}>
            {digits.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleDigitChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                disabled={isLoading}
                autoFocus={i === 0}
                autoComplete={i === 0 ? 'one-time-code' : 'off'}
                className={cn(
                  'w-11 h-14 text-center text-2xl font-semibold rounded-md border',
                  'bg-background text-foreground',
                  'border-input focus:border-primary focus:ring-2 focus:ring-ring focus:outline-none',
                  'transition-all duration-150',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  digit && 'border-primary',
                )}
                aria-label={`Digit ${i + 1}`}
              />
            ))}
          </div>
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          className="w-full"
          disabled={isLoading || code.length !== 6}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
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
          <li>Make sure your authenticator app is synced with the correct time</li>
          <li>The code expires after 30 seconds &mdash; try generating a new one</li>
          <li>Lost access to your authenticator? Use a backup code</li>
        </ul>
      </div>
    </Card>
  )
}
