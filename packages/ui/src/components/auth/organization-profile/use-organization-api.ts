/**
 * Hook for organization API operations
 * Handles SDK client, callbacks, and direct fetch fallbacks
 */

import * as React from 'react'
import type { OrganizationMember, OrganizationApiConfig, OrganizationCallbacks } from './types'

interface UseOrganizationApiProps extends OrganizationApiConfig, OrganizationCallbacks {}

interface UseOrganizationApiReturn {
  fetchMembers: () => Promise<OrganizationMember[]>
  updateOrganization: (data: { name?: string; slug?: string; description?: string }) => Promise<void>
  inviteMember: (email: string, role: 'admin' | 'member') => Promise<void>
  updateMemberRole: (memberId: string, role: 'admin' | 'member') => Promise<void>
  removeMember: (memberId: string) => Promise<void>
  deleteOrganization: () => Promise<void>
}

export function useOrganizationApi({
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  organizationId,
  onUpdateOrganization,
  onFetchMembers,
  onInviteMember,
  onUpdateMemberRole,
  onRemoveMember,
  onDeleteOrganization,
}: UseOrganizationApiProps): UseOrganizationApiReturn {
  const fetchMembers = React.useCallback(async (): Promise<OrganizationMember[]> => {
    if (januaClient) {
      const response = await januaClient.organizations.listMembers(organizationId)
      return Array.isArray(response) ? response : (response.data || [])
    }

    if (onFetchMembers) {
      return onFetchMembers()
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}/members`, {
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Failed to fetch members')
    }

    const data = await response.json()
    return data.data || data
  }, [januaClient, apiUrl, organizationId, onFetchMembers])

  const updateOrganization = React.useCallback(async (
    data: { name?: string; slug?: string; description?: string }
  ): Promise<void> => {
    if (januaClient) {
      await januaClient.organizations.updateOrganization(organizationId, data)
      return
    }

    if (onUpdateOrganization) {
      await onUpdateOrganization(data)
      return
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error('Failed to update organization')
    }
  }, [januaClient, apiUrl, organizationId, onUpdateOrganization])

  const inviteMember = React.useCallback(async (
    email: string,
    role: 'admin' | 'member'
  ): Promise<void> => {
    if (januaClient) {
      await januaClient.organizations.inviteMember(organizationId, { email, role })
      return
    }

    if (onInviteMember) {
      await onInviteMember(email, role)
      return
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}/members/invite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, role }),
    })

    if (!response.ok) {
      throw new Error('Failed to invite member')
    }
  }, [januaClient, apiUrl, organizationId, onInviteMember])

  const updateMemberRole = React.useCallback(async (
    memberId: string,
    role: 'admin' | 'member'
  ): Promise<void> => {
    if (januaClient) {
      await januaClient.organizations.updateMemberRole(organizationId, memberId, role)
      return
    }

    if (onUpdateMemberRole) {
      await onUpdateMemberRole(memberId, role)
      return
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}/members/${memberId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ role }),
    })

    if (!response.ok) {
      throw new Error('Failed to update member role')
    }
  }, [januaClient, apiUrl, organizationId, onUpdateMemberRole])

  const removeMember = React.useCallback(async (memberId: string): Promise<void> => {
    if (januaClient) {
      await januaClient.organizations.removeMember(organizationId, memberId)
      return
    }

    if (onRemoveMember) {
      await onRemoveMember(memberId)
      return
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}/members/${memberId}`, {
      method: 'DELETE',
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Failed to remove member')
    }
  }, [januaClient, apiUrl, organizationId, onRemoveMember])

  const deleteOrganization = React.useCallback(async (): Promise<void> => {
    if (januaClient) {
      await januaClient.organizations.deleteOrganization(organizationId)
      return
    }

    if (onDeleteOrganization) {
      await onDeleteOrganization()
      return
    }

    // Fallback to direct fetch
    const response = await fetch(`${apiUrl}/api/v1/organizations/${organizationId}`, {
      method: 'DELETE',
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Failed to delete organization')
    }
  }, [januaClient, apiUrl, organizationId, onDeleteOrganization])

  return {
    fetchMembers,
    updateOrganization,
    inviteMember,
    updateMemberRole,
    removeMember,
    deleteOrganization,
  }
}
