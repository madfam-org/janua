import * as React from 'react'
import { Fingerprint, Loader2 } from 'lucide-react'
import { Button } from '../button'
import { cn } from '../../lib/utils'

export interface PasskeyButtonProps {
  /** Callback with the WebAuthn credential */
  onAuthenticate?: (credential: any) => Promise<void>
  /** Janua SDK client */
  januaClient?: any
  /** API URL fallback */
  apiUrl?: string
  disabled?: boolean
  className?: string
}

/**
 * "Sign in with Passkey" button.
 * Only renders if the browser supports WebAuthn.
 * Calls navigator.credentials.get() to initiate passkey auth.
 */
export function PasskeyButton({
  onAuthenticate,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  disabled,
  className,
}: PasskeyButtonProps) {
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [supported, setSupported] = React.useState(false)

  React.useEffect(() => {
    // Check WebAuthn support
    setSupported(
      typeof window !== 'undefined' &&
      !!window.PublicKeyCredential &&
      typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === 'function',
    )
  }, [])

  if (!supported) return null

  const handleClick = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Step 1: Get challenge from server
      let options: PublicKeyCredentialRequestOptions

      if (januaClient) {
        const challengeResponse = await januaClient.auth.getPasskeyChallenge()
        options = challengeResponse.options
      } else {
        const response = await fetch(`${apiUrl}/api/v1/auth/passkey/challenge`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        })
        if (!response.ok) throw new Error('Failed to get passkey challenge')
        const data = await response.json()
        options = data.options
      }

      // Step 2: Call WebAuthn API
      const credential = await navigator.credentials.get({
        publicKey: options,
      })

      // Step 3: Send credential to server
      if (onAuthenticate) {
        await onAuthenticate(credential)
      } else if (januaClient) {
        await januaClient.auth.verifyPasskey(credential)
      } else {
        await fetch(`${apiUrl}/api/v1/auth/passkey/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ credential }),
        })
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'NotAllowedError') {
        setError('Passkey authentication was cancelled')
      } else {
        setError('Passkey authentication failed')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className={className}>
      <Button
        type="button"
        variant="outline"
        className={cn('w-full gap-2')}
        onClick={handleClick}
        disabled={disabled || isLoading}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Fingerprint className="w-4 h-4" />
        )}
        Sign in with Passkey
      </Button>
      {error && (
        <p className="text-xs text-destructive mt-1 text-center">{error}</p>
      )}
    </div>
  )
}
