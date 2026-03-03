import { useState, useCallback } from 'react'
import { useJanua } from '../provider'
import type { JanuaUser } from '../types'

export interface UseUserReturn {
  /** Current user data */
  user: JanuaUser | null
  /** Whether the user data is loading */
  isLoading: boolean
  /** Update the current user's profile */
  updateUser: (data: {
    firstName?: string
    lastName?: string
    username?: string
  }) => Promise<void>
}

/**
 * Hook for accessing and updating user data
 *
 * Provides the current user from context and a method to update
 * user profile data via the Janua API.
 *
 * @example
 * ```tsx
 * function ProfileEditor() {
 *   const { user, updateUser, isLoading } = useUser();
 *
 *   const handleSave = async () => {
 *     await updateUser({ firstName: 'Jane', lastName: 'Doe' });
 *   };
 *
 *   return <button onClick={handleSave} disabled={isLoading}>Save</button>;
 * }
 * ```
 */
export function useUser(): UseUserReturn {
  const { user, client, isLoading: contextLoading, refreshSession } = useJanua()
  const [isUpdating, setIsUpdating] = useState(false)

  const updateUser = useCallback(
    async (data: { firstName?: string; lastName?: string; username?: string }) => {
      setIsUpdating(true)
      try {
        await client.updateUser({
          first_name: data.firstName,
          last_name: data.lastName,
        })
        // Refresh session to get updated user data into context
        await refreshSession()
      } finally {
        setIsUpdating(false)
      }
    },
    [client, refreshSession]
  )

  return {
    user,
    isLoading: contextLoading || isUpdating,
    updateUser,
  }
}
