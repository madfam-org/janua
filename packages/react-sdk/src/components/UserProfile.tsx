import React, { useCallback } from 'react'
import { UserProfile as UIUserProfile } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface UserProfileProps {
  /** Optional custom class name */
  className?: string
  /** Callback after sign-out */
  onSignOut?: () => void
  /** Show organization section */
  showOrganization?: boolean
  /** Show sessions section */
  showSessions?: boolean
  /** Allow profile editing */
  allowEdit?: boolean
  /** Show security tab */
  showSecurityTab?: boolean
  /** Show danger zone */
  showDangerZone?: boolean
}

/**
 * Parse a full name into first and last name components
 */
function parseFullName(name: string | null): { firstName: string; lastName: string } {
  if (!name) return { firstName: '', lastName: '' }
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: '' }
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(' '),
  }
}

/**
 * UserProfile component - thin wrapper around @janua/ui UserProfile
 *
 * Injects user data from Janua context and maps to the @janua/ui
 * UserProfile props interface.
 */
export function UserProfile({
  className,
  onSignOut,
  allowEdit = true,
  showSecurityTab = true,
  showDangerZone = true,
}: UserProfileProps) {
  const { user, signOut, client } = useJanua()

  const handleSignOut = useCallback(async () => {
    await signOut()
    onSignOut?.()
  }, [signOut, onSignOut])

  const handleUpdateProfile = useCallback(
    async (data: { firstName?: string; lastName?: string; username?: string; phone?: string }) => {
      await client.updateUser({
        first_name: data.firstName,
        last_name: data.lastName,
      })
    },
    [client]
  )

  if (!user) {
    return (
      <div className={className}>
        <p>Not authenticated</p>
      </div>
    )
  }

  const { firstName, lastName } = parseFullName(user.name)

  return (
    <UIUserProfile
      className={className}
      user={{
        id: user.id,
        email: user.email,
        firstName: firstName || undefined,
        lastName: lastName || undefined,
        avatarUrl: user.picture,
        emailVerified: user.email_verified,
        twoFactorEnabled: user.mfa_enabled,
        createdAt: user.created_at ? new Date(user.created_at) : undefined,
      }}
      onUpdateProfile={allowEdit ? handleUpdateProfile : undefined}
      showSecurityTab={showSecurityTab}
      showDangerZone={showDangerZone}
    />
  )
}
