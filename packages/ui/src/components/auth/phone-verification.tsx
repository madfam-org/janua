import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { cn } from '../../lib/utils'

export interface PhoneVerificationProps {
  /** Optional custom class name */
  className?: string
  /** Phone number being verified */
  phoneNumber: string
  /** Current step in the verification flow */
  step?: 'send' | 'verify' | 'success'
  /** Callback to send verification code */
  onSendCode?: (phoneNumber: string) => Promise<void>
  /** Callback to verify code */
  onVerifyCode?: (code: string) => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Callback when verification is complete */
  onComplete?: () => void
  /** Custom logo URL */
  logoUrl?: string
}

export function PhoneVerification({
  className,
  phoneNumber: initialPhoneNumber,
  step: initialStep = 'send',
  onSendCode,
  onVerifyCode,
  onError,
  onComplete,
  logoUrl,
}: PhoneVerificationProps) {
  const [step, setStep] = React.useState(initialStep)
  const [phoneNumber, setPhoneNumber] = React.useState(initialPhoneNumber)
  const [verificationCode, setVerificationCode] = React.useState('')
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

  // Auto-submit when 6 digits entered
  React.useEffect(() => {
    if (verificationCode.length === 6 && !isLoading && step === 'verify') {
      handleVerifyCode(new Event('submit') as any)
    }
  }, [verificationCode])

  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onSendCode) return

    setIsLoading(true)
    setError(null)

    try {
      await onSendCode(phoneNumber)
      setStep('verify')
      setResendCooldown(60) // 60 second cooldown
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to send verification code')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onVerifyCode) return

    setIsLoading(true)
    setError(null)

    try {
      await onVerifyCode(verificationCode)
      setStep('success')
      onComplete?.()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Invalid verification code')
      setError(error.message)
      onError?.(error)
      setAttempts((prev) => prev + 1)
      setVerificationCode('') // Clear code on error
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (!onSendCode || resendCooldown > 0) return

    setIsLoading(true)
    setError(null)

    try {
      await onSendCode(phoneNumber)
      setResendCooldown(60) // 60 second cooldown
      setVerificationCode('')
      setAttempts(0)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to resend code')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const formatPhoneNumber = (number: string) => {
    // Basic formatting for display (handles US format)
    const cleaned = number.replace(/\D/g, '')
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`
    }
    if (cleaned.length === 11 && cleaned[0] === '1') {
      return `+1 (${cleaned.slice(1, 4)}) ${cleaned.slice(4, 7)}-${cleaned.slice(7)}`
    }
    return number
  }

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-8" />
        </div>
      )}

      {/* Send Code Step */}
      {step === 'send' && (
        <>
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-primary/10 p-3">
                <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-bold">Verify your phone number</h2>
            <p className="text-sm text-muted-foreground mt-2">
              We'll send a verification code to your phone number
            </p>
          </div>

          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSendCode} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="phoneNumber">Phone number</Label>
              <Input
                id="phoneNumber"
                type="tel"
                placeholder="+1 (555) 123-4567"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
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
                'Send verification code'
              )}
            </Button>
          </form>
        </>
      )}

      {/* Verify Code Step */}
      {step === 'verify' && (
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
            <h2 className="text-2xl font-bold">Enter verification code</h2>
            <p className="text-sm text-muted-foreground mt-2">
              We sent a 6-digit code to
              <br />
              <span className="font-medium text-foreground">{formatPhoneNumber(phoneNumber)}</span>
            </p>
          </div>

          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
              {error}
              {attempts >= 3 && (
                <p className="mt-2">
                  Having trouble? Try requesting a new code.
                </p>
              )}
            </div>
          )}

          <form onSubmit={handleVerifyCode} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="verificationCode">Verification code</Label>
              <Input
                id="verificationCode"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                placeholder="000000"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                required
                disabled={isLoading}
                autoFocus
                autoComplete="one-time-code"
                className="text-center text-2xl tracking-widest"
              />
              <p className="text-xs text-muted-foreground text-center">
                Enter the 6-digit code from your SMS
              </p>
            </div>

            <Button
              type="submit"
              className="w-full"
              disabled={isLoading || verificationCode.length !== 6}
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Verifying...
                </>
              ) : (
                'Verify phone number'
              )}
            </Button>

            <div className="text-center space-y-2">
              <button
                type="button"
                className="text-sm text-primary hover:underline disabled:opacity-50 disabled:no-underline"
                onClick={handleResendCode}
                disabled={resendCooldown > 0 || isLoading}
              >
                {resendCooldown > 0
                  ? `Resend code in ${resendCooldown}s`
                  : 'Resend code'}
              </button>

              <div>
                <button
                  type="button"
                  className="text-sm text-muted-foreground hover:text-foreground"
                  onClick={() => setStep('send')}
                >
                  Use a different phone number
                </button>
              </div>
            </div>
          </form>

          <div className="mt-6 bg-muted rounded-lg p-4">
            <h4 className="text-sm font-medium mb-2">Didn't receive the code?</h4>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>• Check that you entered the correct phone number</li>
              <li>• Wait a few moments for the SMS to arrive</li>
              <li>• Make sure you have cellular service</li>
              <li>• Try requesting a new code</li>
            </ul>
          </div>
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
            <h2 className="text-2xl font-bold">Phone verified!</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Your phone number <span className="font-medium text-foreground">{formatPhoneNumber(phoneNumber)}</span> has been successfully verified.
            </p>
          </div>

          {onComplete && (
            <Button className="w-full" onClick={onComplete}>
              Continue
            </Button>
          )}
        </>
      )}
    </Card>
  )
}
