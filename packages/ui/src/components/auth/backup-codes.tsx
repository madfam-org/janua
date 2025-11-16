import * as React from 'react'
import { Button } from '../button'
import { Card } from '../card'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface BackupCodesProps {
  /** Optional custom class name */
  className?: string
  /** List of backup codes with usage status */
  backupCodes?: Array<{
    code: string
    used: boolean
  }>
  /** Callback to fetch backup codes */
  onFetchCodes?: () => Promise<Array<{
    code: string
    used: boolean
  }>>
  /** Callback to regenerate backup codes */
  onRegenerateCodes?: () => Promise<Array<{
    code: string
    used: boolean
  }>>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Allow regeneration of codes */
  allowRegeneration?: boolean
  /** Show download option */
  showDownload?: boolean
}

export function BackupCodes({
  className,
  backupCodes: initialBackupCodes,
  onFetchCodes,
  onRegenerateCodes,
  onError,
  allowRegeneration = true,
  showDownload = true,
}: BackupCodesProps) {
  const [backupCodes, setBackupCodes] = React.useState(initialBackupCodes)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [copiedCode, setCopiedCode] = React.useState<string | null>(null)
  const [showRegenerateConfirm, setShowRegenerateConfirm] = React.useState(false)

  // Fetch codes on mount if not provided
  React.useEffect(() => {
    if (!backupCodes && onFetchCodes) {
      setIsLoading(true)
      onFetchCodes()
        .then(setBackupCodes)
        .catch((err) => {
          const error = err instanceof Error ? err : new Error('Failed to fetch backup codes')
          setError(error.message)
          onError?.(error)
        })
        .finally(() => setIsLoading(false))
    }
  }, [backupCodes, onFetchCodes, onError])

  const handleCopyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedCode(code)
      setTimeout(() => setCopiedCode(null), 2000)
    } catch (err) {
      console.error('Failed to copy code:', err)
    }
  }

  const handleDownloadCodes = () => {
    if (!backupCodes) return

    const unusedCodes = backupCodes.filter((c) => !c.used).map((c) => c.code)
    const usedCodes = backupCodes.filter((c) => c.used).map((c) => c.code)

    const content = `Plinto Backup Codes
Generated: ${new Date().toISOString()}

UNUSED CODES (${unusedCodes.length}):
${unusedCodes.join('\n')}

${usedCodes.length > 0 ? `USED CODES (${usedCodes.length}):\n${usedCodes.join('\n')}` : ''}

⚠️ IMPORTANT:
- Store these codes in a secure location
- Each code can only be used once
- If you run out of codes, you can regenerate a new set
- Regenerating codes will invalidate all previous codes
`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `plinto-backup-codes-${Date.now()}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleRegenerateCodes = async () => {
    if (!onRegenerateCodes) return

    setIsLoading(true)
    setError(null)
    setShowRegenerateConfirm(false)

    try {
      const newCodes = await onRegenerateCodes()
      setBackupCodes(newCodes)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to regenerate backup codes')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading && !backupCodes) {
    return (
      <Card className={cn('w-full max-w-2xl mx-auto p-6', className)}>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      </Card>
    )
  }

  if (!backupCodes) {
    return (
      <Card className={cn('w-full max-w-2xl mx-auto p-6', className)}>
        <div className="text-center py-12">
          <p className="text-destructive">Failed to load backup codes</p>
        </div>
      </Card>
    )
  }

  const unusedCount = backupCodes.filter((c) => !c.used).length
  const usedCount = backupCodes.filter((c) => c.used).length

  return (
    <Card className={cn('w-full max-w-2xl mx-auto p-6', className)}>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between mb-2">
          <h2 className="text-2xl font-bold">Backup codes</h2>
          <div className="flex gap-2">
            <Badge variant={unusedCount > 0 ? 'default' : 'destructive'}>
              {unusedCount} unused
            </Badge>
            {usedCount > 0 && (
              <Badge variant="secondary">{usedCount} used</Badge>
            )}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Use backup codes to sign in when you don't have access to your authenticator app
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Warning if running low */}
      {unusedCount <= 2 && unusedCount > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-6">
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
              <p className="font-medium text-yellow-800 dark:text-yellow-200">Running low on backup codes</p>
              <p className="text-yellow-700 dark:text-yellow-300 mt-1">
                You only have {unusedCount} backup {unusedCount === 1 ? 'code' : 'codes'} remaining. Consider regenerating a new set.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* No codes left warning */}
      {unusedCount === 0 && (
        <div className="bg-destructive/15 border border-destructive/50 rounded-lg p-4 mb-6">
          <div className="flex gap-3">
            <svg
              className="w-5 h-5 text-destructive shrink-0 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div className="text-sm">
              <p className="font-medium text-destructive">No backup codes available</p>
              <p className="text-destructive/80 mt-1">
                All your backup codes have been used. Regenerate a new set to maintain account recovery access.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Backup Codes Grid */}
      <div className="space-y-3 mb-6">
        {backupCodes.map(({ code, used }, index) => (
          <div
            key={code}
            className={cn(
              'flex items-center justify-between py-3 px-4 rounded-lg border transition-colors',
              used
                ? 'bg-muted/50 border-muted opacity-60'
                : 'bg-background border-border hover:border-primary/50'
            )}
          >
            <div className="flex items-center gap-3 flex-1">
              <span className="text-sm text-muted-foreground font-medium w-8">
                #{index + 1}
              </span>
              <code
                className={cn(
                  'font-mono font-medium text-lg tracking-wider',
                  used ? 'line-through text-muted-foreground' : ''
                )}
              >
                {code}
              </code>
              {used && (
                <Badge variant="outline" className="ml-2">
                  Used
                </Badge>
              )}
            </div>
            {!used && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleCopyCode(code)}
                className="shrink-0"
              >
                {copiedCode === code ? (
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
            )}
          </div>
        ))}
      </div>

      {/* Important Notice */}
      <div className="bg-muted rounded-lg p-4 mb-6">
        <h4 className="text-sm font-medium mb-2">⚠️ Important Information</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• Each backup code can only be used once</li>
          <li>• Store these codes in a secure location (password manager, safe, etc.)</li>
          <li>• You can use backup codes to sign in if you lose access to your authenticator app</li>
          <li>• Regenerating codes will invalidate all previous codes, including unused ones</li>
          <li>• Download or copy these codes before leaving this page</li>
        </ul>
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3">
        {showDownload && (
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleDownloadCodes}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Download codes
          </Button>
        )}

        {allowRegeneration && onRegenerateCodes && (
          <>
            {!showRegenerateConfirm ? (
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowRegenerateConfirm(true)}
                disabled={isLoading}
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Regenerate codes
              </Button>
            ) : (
              <div className="flex-1 flex gap-2">
                <Button
                  variant="destructive"
                  className="flex-1"
                  onClick={handleRegenerateCodes}
                  disabled={isLoading}
                >
                  {isLoading ? 'Regenerating...' : 'Confirm regenerate'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowRegenerateConfirm(false)}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Regenerate Warning */}
      {showRegenerateConfirm && (
        <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            <strong>Warning:</strong> Regenerating will invalidate all existing backup codes, including unused ones.
            Make sure you've saved your new codes after regeneration.
          </p>
        </div>
      )}
    </Card>
  )
}
