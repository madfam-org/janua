import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'
import { parseApiError, formatErrorMessage, AUTH_ERRORS } from '../../lib/error-messages'

export interface MFASetupProps {
  /** Optional custom class name */
  className?: string
  /** MFA setup data from server */
  mfaData?: {
    secret: string
    qrCode: string
    backupCodes: string[]
  }
  /** Callback to fetch MFA setup data */
  onFetchSetupData?: () => Promise<{
    secret: string
    qrCode: string
    backupCodes: string[]
  }>
  /** Callback after successful MFA setup */
  onComplete?: (verificationCode: string) => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Callback to cancel setup */
  onCancel?: () => void
  /** Show backup codes step */
  showBackupCodes?: boolean
  /** Plinto client instance for API integration */
  plintoClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
}

export function MFASetup({
  className,
  mfaData: initialMfaData,
  onFetchSetupData,
  onComplete,
  onError,
  onCancel,
  showBackupCodes = true,
  plintoClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: MFASetupProps) {
  const [step, setStep] = React.useState<'scan' | 'verify' | 'backup'>('scan')
  const [mfaData, setMfaData] = React.useState(initialMfaData)
  const [verificationCode, setVerificationCode] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [copiedSecret, setCopiedSecret] = React.useState(false)
  const [downloadedCodes, setDownloadedCodes] = React.useState(false)

  // Fetch MFA data on mount if not provided
  React.useEffect(() => {
    if (!mfaData) {
      setIsLoading(true)

      const fetchData = async () => {
        if (plintoClient) {
          // Use Plinto SDK for MFA setup
          const response = await plintoClient.auth.setupMFA('totp')
          return response
        } else if (onFetchSetupData) {
          // Use custom callback if provided
          return await onFetchSetupData()
        } else {
          // Fallback to direct fetch
          const response = await fetch(`${apiUrl}/api/v1/auth/mfa/setup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ type: 'totp' }),
          })

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}))
            const actionableError = parseApiError(errorData, { status: response.status })
            throw new Error(actionableError.message)
          }

          return await response.json()
        }
      }

      fetchData()
        .then(setMfaData)
        .catch((err) => {
          const actionableError = parseApiError(err, {
            message: err instanceof Error ? err.message : 'Failed to fetch MFA setup data'
          })
          setError(formatErrorMessage(actionableError, true))
          onError?.(new Error(actionableError.message))
        })
        .finally(() => setIsLoading(false))
    }
  }, [mfaData, plintoClient, onFetchSetupData, onError, apiUrl])

  const handleCopySecret = async () => {
    if (!mfaData?.secret) return
    try {
      await navigator.clipboard.writeText(mfaData.secret)
      setCopiedSecret(true)
      setTimeout(() => setCopiedSecret(false), 2000)
    } catch (err) {
      console.error('Failed to copy secret:', err)
    }
  }

  const handleDownloadBackupCodes = () => {
    if (!mfaData?.backupCodes) return

    const content = `Plinto Backup Codes\nGenerated: ${new Date().toISOString()}\n\n${mfaData.backupCodes.join('\n')}\n\nStore these codes securely. Each code can only be used once.`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `plinto-backup-codes-${Date.now()}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    setDownloadedCodes(true)
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      if (plintoClient) {
        // Use Plinto SDK for MFA verification
        await plintoClient.auth.verifyMFA(verificationCode)
      } else if (onComplete) {
        // Use custom callback if provided
        await onComplete(verificationCode)
      } else {
        // Fallback to direct fetch
        const response = await fetch(`${apiUrl}/api/v1/auth/mfa/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ code: verificationCode }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          const actionableError = parseApiError(errorData, { status: response.status })
          throw new Error(actionableError.message)
        }
      }

      if (showBackupCodes && mfaData?.backupCodes) {
        setStep('backup')
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: err instanceof Error ? err.message : 'Invalid MFA verification code'
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading && !mfaData) {
    return (
      <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      </Card>
    )
  }

  if (!mfaData) {
    return (
      <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
        <div className="text-center py-12">
          <p className="text-destructive">Failed to load MFA setup data</p>
        </div>
      </Card>
    )
  }

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Header with Step Indicator */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Set up two-factor authentication</h2>
          <Badge variant={step === 'backup' ? 'default' : 'secondary'}>
            {step === 'scan' ? 'Step 1 of 3' : step === 'verify' ? 'Step 2 of 3' : 'Step 3 of 3'}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Add an extra layer of security to your account
        </p>
      </div>

      {/* Step 1: Scan QR Code */}
      {step === 'scan' && (
        <div className="space-y-6">
          <div>
            <h3 className="font-medium mb-2">1. Scan this QR code</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Use an authenticator app like Google Authenticator, Authy, or 1Password
            </p>

            {/* QR Code */}
            <div className="flex justify-center p-4 bg-white rounded-lg border">
              <img
                src={mfaData.qrCode}
                alt="QR Code for two-factor authentication"
                className="w-48 h-48"
              />
            </div>
          </div>

          {/* Manual Entry */}
          <div>
            <h3 className="font-medium mb-2">Or enter this code manually</h3>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 bg-muted rounded-md font-mono text-sm break-all">
                {mfaData.secret}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopySecret}
                className="shrink-0"
              >
                {copiedSecret ? (
                  <>
                    <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Copied
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    Copy
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Next Button */}
          <div className="flex gap-3">
            {onCancel && (
              <Button variant="outline" onClick={onCancel} className="flex-1">
                Cancel
              </Button>
            )}
            <Button onClick={() => setStep('verify')} className="flex-1">
              Continue
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Verify Code */}
      {step === 'verify' && (
        <form onSubmit={handleVerify} className="space-y-6">
          <div>
            <h3 className="font-medium mb-2">2. Verify your code</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Enter the 6-digit code from your authenticator app
            </p>

            {error && (
              <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-4">
                {error}
              </div>
            )}

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
                autoComplete="one-time-code"
                className="text-center text-2xl tracking-widest"
              />
            </div>
          </div>

          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep('scan')}
              className="flex-1"
            >
              Back
            </Button>
            <Button
              type="submit"
              disabled={isLoading || verificationCode.length !== 6}
              className="flex-1"
            >
              {isLoading ? 'Verifying...' : 'Verify and continue'}
            </Button>
          </div>
        </form>
      )}

      {/* Step 3: Backup Codes */}
      {step === 'backup' && mfaData.backupCodes && (
        <div className="space-y-6">
          <div>
            <h3 className="font-medium mb-2">3. Save your backup codes</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Store these codes in a safe place. You can use them to sign in if you lose access to your authenticator app.
            </p>

            <div className="bg-muted p-4 rounded-lg space-y-2">
              {mfaData.backupCodes.map((code, index) => (
                <div
                  key={code}
                  className="flex items-center justify-between py-2 px-3 bg-background rounded"
                >
                  <span className="text-sm text-muted-foreground">Code {index + 1}</span>
                  <code className="font-mono font-medium">{code}</code>
                </div>
              ))}
            </div>
          </div>

          {/* Warning */}
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <div className="flex gap-3">
              <svg
                className="w-5 h-5 text-yellow-600 dark:text-yellow-500 shrink-0 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="text-sm">
                <p className="font-medium text-yellow-800 dark:text-yellow-200">Important</p>
                <p className="text-yellow-700 dark:text-yellow-300 mt-1">
                  Each backup code can only be used once. After using a code, it will be invalidated.
                </p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full"
              onClick={handleDownloadBackupCodes}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              {downloadedCodes ? 'Downloaded' : 'Download codes'}
            </Button>

            <Button
              className="w-full"
              onClick={() => {
                // Complete the setup
                if (!downloadedCodes) {
                  alert('Please download your backup codes before continuing')
                  return
                }
                // Redirect or close modal
                window.location.href = '/dashboard'
              }}
            >
              Complete setup
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
