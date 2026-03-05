import { useState, useCallback } from 'react'
import { useJanua } from '../provider'

export interface UseMFAReturn {
  /** Enable MFA for the current user. Returns the secret, QR code URI, and backup codes. */
  enable: (type?: string) => Promise<{ secret: string; qr_code: string; backup_codes: string[]; provisioning_uri: string }>
  /** Verify an MFA code */
  verify: (code: string) => Promise<void>
  /** Disable MFA for the current user */
  disable: (password: string) => Promise<void>
  /** Whether an MFA operation is in progress */
  isLoading: boolean
  /** Error from the last MFA operation */
  error: Error | null
}

/**
 * Hook for multi-factor authentication operations
 *
 * Provides methods to enable, verify, and disable MFA
 * for the current user.
 *
 * @example
 * ```tsx
 * function MFASetup() {
 *   const { enable, verify, disable, isLoading, error } = useMFA();
 *
 *   const handleEnable = async () => {
 *     const { secret, qrCode } = await enable('totp');
 *     // Display QR code for user to scan
 *   };
 *
 *   return (
 *     <div>
 *       <button onClick={handleEnable} disabled={isLoading}>Enable MFA</button>
 *       {error && <p>{error.message}</p>}
 *     </div>
 *   );
 * }
 * ```
 */
export function useMFA(): UseMFAReturn {
  const { client } = useJanua()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const enable = useCallback(
    async (type: string = 'totp') => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await client.auth.enableMFA(type)
        return response
      } catch (err) {
        const mfaError = err instanceof Error ? err : new Error('Failed to enable MFA')
        setError(mfaError)
        throw mfaError
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  const verify = useCallback(
    async (code: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await client.auth.verifyMFA({ code })
      } catch (err) {
        const mfaError = err instanceof Error ? err : new Error('MFA verification failed')
        setError(mfaError)
        throw mfaError
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  const disable = useCallback(
    async (password: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await client.auth.disableMFA(password)
      } catch (err) {
        const mfaError = err instanceof Error ? err : new Error('Failed to disable MFA')
        setError(mfaError)
        throw mfaError
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  return {
    enable,
    verify,
    disable,
    isLoading,
    error,
  }
}
