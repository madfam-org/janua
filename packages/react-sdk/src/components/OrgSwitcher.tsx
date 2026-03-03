import React from 'react'
import { OrganizationSwitcher as UIOrganizationSwitcher } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface OrgSwitcherProps {
  /** Optional custom class name */
  className?: string
  /** Callback when organization is switched */
  onSwitchOrganization?: (organization: { id: string; name: string; slug: string }) => void
  /** Callback to create new organization */
  onCreateOrganization?: () => void
  /** Show create organization option */
  showCreateOrganization?: boolean
  /** Show personal workspace option */
  showPersonalWorkspace?: boolean
  /** Callback on error */
  onError?: (error: Error) => void
}

/**
 * OrgSwitcher component - thin wrapper around @janua/ui OrganizationSwitcher
 *
 * Injects the Janua client from context for API calls.
 */
export function OrgSwitcher({
  className,
  onSwitchOrganization,
  onCreateOrganization,
  showCreateOrganization,
  showPersonalWorkspace,
  onError,
}: OrgSwitcherProps) {
  const { client, user } = useJanua()

  return (
    <UIOrganizationSwitcher
      januaClient={client}
      className={className}
      onSwitchOrganization={onSwitchOrganization}
      onCreateOrganization={onCreateOrganization}
      showCreateOrganization={showCreateOrganization}
      showPersonalWorkspace={showPersonalWorkspace}
      personalWorkspace={
        user
          ? { id: user.id, name: user.display_name || user.name || user.email }
          : undefined
      }
      onError={onError}
    />
  )
}
