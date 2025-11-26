/**
 * Organization profile component (refactored)
 *
 * Manages organization settings, members, and deletion through focused sub-components.
 */

import * as React from 'react'
import { Card } from '../../card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../tabs'
import { cn } from '../../../lib/utils'
import { GeneralSettingsTab } from './general-settings-tab'
import { MembersTab } from './members-tab'
import { DangerZoneTab } from './danger-zone-tab'
import { useOrganizationApi } from './use-organization-api'
import type { Organization, OrganizationMember, UserRole, OrganizationCallbacks } from './types'

export interface OrganizationProfileProps extends OrganizationCallbacks {
  /** Optional custom class name */
  className?: string
  /** Organization data */
  organization: Organization
  /** Current user's role in the organization */
  userRole: UserRole
  /** Organization members (optional if januaClient provided) */
  members?: OrganizationMember[]
  /** Janua client instance for API integration */
  januaClient?: {
    organizations: {
      listMembers: (orgId: string) => Promise<{ data?: OrganizationMember[] } | OrganizationMember[]>
      updateOrganization: (orgId: string, data: { name?: string; slug?: string; description?: string }) => Promise<void>
      inviteMember: (orgId: string, data: { email: string; role: string }) => Promise<void>
      updateMemberRole: (orgId: string, memberId: string, role: string) => Promise<void>
      removeMember: (orgId: string, memberId: string) => Promise<void>
      deleteOrganization: (orgId: string) => Promise<void>
    }
  }
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
}

type TabValue = 'general' | 'members' | 'danger'

export function OrganizationProfile({
  className,
  organization,
  userRole,
  members: initialMembers,
  onUpdateOrganization,
  onUploadLogo,
  onFetchMembers,
  onInviteMember,
  onUpdateMemberRole,
  onRemoveMember,
  onDeleteOrganization,
  onError,
  januaClient,
  apiUrl,
}: OrganizationProfileProps) {
  const [activeTab, setActiveTab] = React.useState<TabValue>('general')
  const [members, setMembers] = React.useState<OrganizationMember[] | undefined>(initialMembers)
  const [isLoadingMembers, setIsLoadingMembers] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const canManageSettings = userRole === 'owner' || userRole === 'admin'
  const canManageMembers = userRole === 'owner' || userRole === 'admin'
  const canDeleteOrg = userRole === 'owner'

  // API operations hook
  const api = useOrganizationApi({
    januaClient,
    apiUrl,
    organizationId: organization.id,
    onUpdateOrganization,
    onFetchMembers,
    onInviteMember,
    onUpdateMemberRole,
    onRemoveMember,
    onDeleteOrganization,
  })

  // Fetch members when members tab becomes active
  React.useEffect(() => {
    if (!members && activeTab === 'members') {
      setIsLoadingMembers(true)
      api.fetchMembers()
        .then(setMembers)
        .catch((err) => {
          const error = err instanceof Error ? err : new Error('Failed to fetch members')
          setError(error.message)
          onError?.(error)
        })
        .finally(() => setIsLoadingMembers(false))
    }
  }, [members, activeTab, api, onError])

  const handleError = React.useCallback((err: Error) => {
    setError(err.message)
    onError?.(err)
  }, [onError])

  const handleInviteMember = React.useCallback(async (email: string, role: 'admin' | 'member') => {
    await api.inviteMember(email, role)
    // Refresh members list
    const updatedMembers = await api.fetchMembers()
    setMembers(updatedMembers)
  }, [api])

  return (
    <Card className={cn('w-full max-w-4xl mx-auto p-6', className)}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Organization settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your organization profile and members
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)}>
        <TabsList className="mb-6">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          {canDeleteOrg && <TabsTrigger value="danger">Danger Zone</TabsTrigger>}
        </TabsList>

        <TabsContent value="general">
          <GeneralSettingsTab
            organization={organization}
            canManageSettings={canManageSettings}
            onUpdateOrganization={api.updateOrganization}
            onUploadLogo={onUploadLogo}
            onError={handleError}
          />
        </TabsContent>

        <TabsContent value="members">
          <MembersTab
            members={members}
            isLoading={isLoadingMembers}
            canManageMembers={canManageMembers}
            onInviteMember={onInviteMember ? handleInviteMember : undefined}
            onUpdateMemberRole={onUpdateMemberRole ? api.updateMemberRole : undefined}
            onRemoveMember={onRemoveMember ? api.removeMember : undefined}
            onMembersChange={setMembers}
            onError={handleError}
          />
        </TabsContent>

        {canDeleteOrg && (
          <TabsContent value="danger">
            <DangerZoneTab
              organizationSlug={organization.slug}
              onDeleteOrganization={onDeleteOrganization ? api.deleteOrganization : undefined}
              onError={handleError}
            />
          </TabsContent>
        )}
      </Tabs>
    </Card>
  )
}
