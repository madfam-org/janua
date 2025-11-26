/**
 * Shared types for organization profile components
 */

export interface OrganizationMember {
  /** Member ID */
  id: string
  /** Member email */
  email: string
  /** Member name */
  name?: string
  /** Member role */
  role: 'owner' | 'admin' | 'member'
  /** Member avatar URL */
  avatarUrl?: string
  /** Join date */
  joinedAt?: Date
  /** Invite status */
  status?: 'active' | 'invited' | 'suspended'
}

export interface Organization {
  id: string
  name: string
  slug: string
  logoUrl?: string
  description?: string
  createdAt?: Date
  memberCount?: number
}

export type UserRole = 'owner' | 'admin' | 'member'

export interface OrganizationApiConfig {
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
  /** Organization ID */
  organizationId: string
}

export interface OrganizationCallbacks {
  /** Callback to update organization */
  onUpdateOrganization?: (data: { name?: string; slug?: string; description?: string }) => Promise<void>
  /** Callback to upload organization logo */
  onUploadLogo?: (file: File) => Promise<string>
  /** Callback to fetch members */
  onFetchMembers?: () => Promise<OrganizationMember[]>
  /** Callback to invite member */
  onInviteMember?: (email: string, role: 'admin' | 'member') => Promise<void>
  /** Callback to update member role */
  onUpdateMemberRole?: (memberId: string, role: 'admin' | 'member') => Promise<void>
  /** Callback to remove member */
  onRemoveMember?: (memberId: string) => Promise<void>
  /** Callback to delete organization */
  onDeleteOrganization?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
}
