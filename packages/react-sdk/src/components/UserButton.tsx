import React, { useCallback, useMemo, useState } from 'react'
import type { JanuaAccountSwitchOptions } from '@janua/typescript-sdk'
import { UserButton as UIUserButton } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface UserButtonProps {
  /** Optional custom class name */
  className?: string
  /** Show manage account option */
  showManageAccount?: boolean
  /** Custom manage account URL */
  manageAccountUrl?: string
  /** Show organization switcher */
  showOrganizations?: boolean
  /** Active organization name to display */
  activeOrganization?: string
  /** Registered RP client/callback. Without it no switch action is displayed. */
  switchAccountOptions?: JanuaAccountSwitchOptions
}

/**
 * UserButton component - thin wrapper around @janua/ui UserButton
 *
 * Injects user data from Janua context and maps JanuaUser fields
 * to the @janua/ui UserButton props format.
 */
export function UserButton({
  className,
  showManageAccount,
  manageAccountUrl,
  showOrganizations,
  activeOrganization,
  switchAccountOptions,
}: UserButtonProps) {
  const { client, user, signOut } = useJanua()
  const [switchError, setSwitchError] = useState(false)

  const handleSwitchAccount = useCallback(async () => {
    if (!switchAccountOptions) return
    setSwitchError(false)
    try { await client.auth.switchAccount(switchAccountOptions) }
    catch { setSwitchError(true) }
  }, [client, switchAccountOptions])

  const handleSignOut = useCallback(async () => {
    await signOut()
  }, [signOut])

  const mappedUser = useMemo(() => {
    if (!user) return null

    // Parse full name into first/last
    const nameParts = user.name ? user.name.trim().split(/\s+/) : []
    const firstName = nameParts[0] || undefined
    const lastName = nameParts.length > 1 ? nameParts.slice(1).join(' ') : undefined

    return {
      id: user.id,
      email: user.email,
      firstName,
      lastName,
      avatarUrl: user.picture,
    }
  }, [user])

  if (!mappedUser) {
    return null
  }

  return (
    <>
      <UIUserButton
        user={mappedUser}
        onSignOut={handleSignOut}
        onSwitchAccount={switchAccountOptions?.clientId && switchAccountOptions.redirectUri ? handleSwitchAccount : undefined}
        showManageAccount={showManageAccount}
        manageAccountUrl={manageAccountUrl}
        showOrganizations={showOrganizations}
        activeOrganization={activeOrganization}
        className={className}
      />
      {switchError && <span role="alert">Could not open account selection. Your current session is unchanged.</span>}
    </>
  )
}
