import { useState, useCallback, useMemo } from 'react'
import { checkWebAuthnSupport } from '@janua/typescript-sdk'
import { useJanua } from '../provider'

export interface UsePasskeyReturn {
  /** Register a new passkey for the current user */
  register: (name?: string) => Promise<void>
  /** Authenticate with a passkey */
  authenticate: (email?: string) => Promise<void>
  /** Whether WebAuthn/passkeys are supported in this browser */
  isSupported: boolean
  /** Whether a passkey operation is in progress */
  isLoading: boolean
  /** Error from the last passkey operation */
  error: Error | null
}

/**
 * Hook for passkey (WebAuthn/FIDO2) operations
 *
 * Provides methods to register and authenticate with passkeys,
 * with browser support detection.
 *
 * @example
 * ```tsx
 * function PasskeySection() {
 *   const { register, authenticate, isSupported, isLoading, error } = usePasskey();
 *
 *   if (!isSupported) return <p>Passkeys not supported in this browser.</p>;
 *
 *   return (
 *     <div>
 *       <button onClick={() => register('My Laptop')} disabled={isLoading}>
 *         Register Passkey
 *       </button>
 *       <button onClick={() => authenticate()} disabled={isLoading}>
 *         Sign in with Passkey
 *       </button>
 *       {error && <p>{error.message}</p>}
 *     </div>
 *   );
 * }
 * ```
 */
export function usePasskey(): UsePasskeyReturn {
  const { client } = useJanua()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const isSupported = useMemo(() => {
    const support = checkWebAuthnSupport()
    return support.available
  }, [])

  const register = useCallback(
    async (name?: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await client.registerPasskey(name)
      } catch (err) {
        const passError = err instanceof Error ? err : new Error('Passkey registration failed')
        setError(passError)
        throw passError
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  const authenticate = useCallback(
    async (email?: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await client.signInWithPasskey(email)
      } catch (err) {
        const passError = err instanceof Error ? err : new Error('Passkey authentication failed')
        setError(passError)
        throw passError
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  return {
    register,
    authenticate,
    isSupported,
    isLoading,
    error,
  }
}
