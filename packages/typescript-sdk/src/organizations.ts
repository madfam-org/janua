/**
 * Organization management module for the Plinto TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  Organization,
  OrganizationCreateRequest,
  OrganizationUpdateRequest,
  OrganizationMember,
  OrganizationInvitation,
  OrganizationInviteRequest,
  OrganizationRole,
  OrganizationListParams,
  PaginatedResponse
} from './types';
import { ValidationError } from './errors';
import { ValidationUtils } from './utils';

/**
 * Organization management operations
 */
export class Organizations {
  constructor(private http: HttpClient) {}

  /**
   * Create a new organization
   */
  async createOrganization(request: OrganizationCreateRequest): Promise<Organization> {
    // Validate input
    if (!request.name || request.name.trim().length === 0) {
      throw new ValidationError('Organization name is required');
    }

    if (request.name.length > 200) {
      throw new ValidationError('Organization name must be 200 characters or less');
    }

    if (!ValidationUtils.isValidSlug(request.slug)) {
      throw new ValidationError('Invalid slug format. Use lowercase letters, numbers, and hyphens only');
    }

    if (request.description && request.description.length > 1000) {
      throw new ValidationError('Organization description must be 1000 characters or less');
    }

    if (request.billing_email && !ValidationUtils.isValidEmail(request.billing_email)) {
      throw new ValidationError('Invalid billing email format');
    }

    const response = await this.http.post<Organization>('/api/v1/organizations/', request);
    return response.data;
  }

  /**
   * List user's organizations
   */
  async listOrganizations(): Promise<Organization[]> {
    const response = await this.http.get<Organization[]>('/api/v1/organizations/');
    return response.data;
  }

  /**
   * Get organization by ID
   */
  async getOrganization(organizationId: string): Promise<Organization> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.get<Organization>(`/api/v1/organizations/${organizationId}`);
    return response.data;
  }

  /**
   * Update organization
   */
  async updateOrganization(
    organizationId: string,
    request: OrganizationUpdateRequest
  ): Promise<Organization> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    // Validate input
    if (request.name !== undefined) {
      if (!request.name || request.name.trim().length === 0) {
        throw new ValidationError('Organization name cannot be empty');
      }
      if (request.name.length > 200) {
        throw new ValidationError('Organization name must be 200 characters or less');
      }
    }

    if (request.description !== undefined && request.description && request.description.length > 1000) {
      throw new ValidationError('Organization description must be 1000 characters or less');
    }

    if (request.logo_url && !ValidationUtils.isValidUrl(request.logo_url)) {
      throw new ValidationError('Invalid logo URL format');
    }

    if (request.billing_email && !ValidationUtils.isValidEmail(request.billing_email)) {
      throw new ValidationError('Invalid billing email format');
    }

    const response = await this.http.patch<Organization>(`/api/v1/organizations/${organizationId}`, request);
    return response.data;
  }

  /**
   * Delete organization (owner only)
   */
  async deleteOrganization(organizationId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/organizations/${organizationId}`);
    return response.data;
  }

  // Member Management

  /**
   * List organization members
   */
  async listMembers(organizationId: string): Promise<OrganizationMember[]> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.get<OrganizationMember[]>(`/api/v1/organizations/${organizationId}/members`);
    return response.data;
  }

  /**
   * Update member role
   */
  async updateMemberRole(
    organizationId: string,
    userId: string,
    role: OrganizationRole
  ): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    if (!ValidationUtils.isValidUUID(userId)) {
      throw new ValidationError('Invalid user ID format');
    }

    if (!Object.values(OrganizationRole).includes(role)) {
      throw new ValidationError('Invalid role');
    }

    const response = await this.http.put<{ message: string }>(
      `/api/v1/organizations/${organizationId}/members/${userId}/role`,
      { role }
    );
    return response.data;
  }

  /**
   * Remove member from organization
   */
  async removeMember(organizationId: string, userId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    if (!ValidationUtils.isValidUUID(userId)) {
      throw new ValidationError('Invalid user ID format');
    }

    const response = await this.http.delete<{ message: string }>(
      `/api/v1/organizations/${organizationId}/members/${userId}`
    );
    return response.data;
  }

  // Invitation Management

  /**
   * Invite member to organization
   */
  async inviteMember(
    organizationId: string,
    request: OrganizationInviteRequest
  ): Promise<{
    message: string;
    invitation_id: string;
    expires_at: string;
  }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    // Validate input
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    if (!Object.values(OrganizationRole).includes(request.role)) {
      throw new ValidationError('Invalid role');
    }

    if (request.message && request.message.length > 500) {
      throw new ValidationError('Invitation message must be 500 characters or less');
    }

    const response = await this.http.post<{
      message: string;
      invitation_id: string;
      expires_at: string;
    }>(`/api/v1/organizations/${organizationId}/invite`, request);
    return response.data;
  }

  /**
   * Accept organization invitation
   */
  async acceptInvitation(token: string): Promise<{
    message: string;
    organization: {
      id: string;
      name: string;
      slug: string;
    };
  }> {
    if (!token) {
      throw new ValidationError('Invitation token is required');
    }

    const response = await this.http.post<{
      message: string;
      organization: {
        id: string;
        name: string;
        slug: string;
      };
    }>(`/api/v1/organizations/invitations/${token}/accept`);
    return response.data;
  }

  /**
   * List organization invitations
   */
  async listInvitations(
    organizationId: string,
    status?: 'pending' | 'accepted' | 'expired'
  ): Promise<OrganizationInvitation[]> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const params: Record<string, any> = {};
    if (status) {
      params.status = status;
    }

    const response = await this.http.get<OrganizationInvitation[]>(
      `/api/v1/organizations/${organizationId}/invitations`,
      { params }
    );
    return response.data;
  }

  /**
   * Revoke organization invitation
   */
  async revokeInvitation(organizationId: string, invitationId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    if (!ValidationUtils.isValidUUID(invitationId)) {
      throw new ValidationError('Invalid invitation ID format');
    }

    const response = await this.http.delete<{ message: string }>(
      `/api/v1/organizations/${organizationId}/invitations/${invitationId}`
    );
    return response.data;
  }

  // Role Management

  /**
   * Create custom role
   */
  async createCustomRole(
    organizationId: string,
    request: {
      name: string;
      description?: string;
      permissions: string[];
    }
  ): Promise<{
    id: string;
    name: string;
    description?: string;
    permissions: string[];
    is_system: boolean;
    created_at: string;
    updated_at: string;
  }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    // Validate input
    if (!request.name || request.name.trim().length === 0) {
      throw new ValidationError('Role name is required');
    }

    if (request.name.length > 100) {
      throw new ValidationError('Role name must be 100 characters or less');
    }

    if (request.description && request.description.length > 500) {
      throw new ValidationError('Role description must be 500 characters or less');
    }

    if (!Array.isArray(request.permissions)) {
      throw new ValidationError('Permissions must be an array');
    }

    const response = await this.http.post(`/api/v1/organizations/${organizationId}/roles`, request);
    return response.data;
  }

  /**
   * List organization roles (built-in and custom)
   */
  async listRoles(organizationId: string): Promise<Array<{
    id: string;
    name: string;
    description?: string;
    permissions: string[];
    is_system: boolean;
    created_at: string;
    updated_at: string;
  }>> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.get(`/api/v1/organizations/${organizationId}/roles`);
    return response.data;
  }

  /**
   * Delete custom role
   */
  async deleteCustomRole(organizationId: string, roleId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    if (!ValidationUtils.isValidUUID(roleId)) {
      throw new ValidationError('Invalid role ID format');
    }

    const response = await this.http.delete<{ message: string }>(
      `/api/v1/organizations/${organizationId}/roles/${roleId}`
    );
    return response.data;
  }

  /**
   * Transfer organization ownership
   */
  async transferOwnership(organizationId: string, newOwnerId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    if (!ValidationUtils.isValidUUID(newOwnerId)) {
      throw new ValidationError('Invalid user ID format');
    }

    const response = await this.http.post<{ message: string }>(
      `/api/v1/organizations/${organizationId}/transfer-ownership`,
      { new_owner_id: newOwnerId }
    );
    return response.data;
  }

  // Helper Methods

  /**
   * Check if user has specific role in organization
   */
  hasRole(organization: Organization, role: OrganizationRole): boolean {
    return organization.user_role === role;
  }

  /**
   * Check if user has minimum role level in organization
   */
  hasMinimumRole(organization: Organization, minimumRole: OrganizationRole): boolean {
    const roleHierarchy = {
      [OrganizationRole.VIEWER]: 0,
      [OrganizationRole.MEMBER]: 1,
      [OrganizationRole.ADMIN]: 2,
      [OrganizationRole.OWNER]: 3
    };

    const userRoleLevel = roleHierarchy[organization.user_role as OrganizationRole] || 0;
    const minimumRoleLevel = roleHierarchy[minimumRole];

    return userRoleLevel >= minimumRoleLevel;
  }

  /**
   * Check if user can manage members
   */
  canManageMembers(organization: Organization): boolean {
    return this.hasMinimumRole(organization, OrganizationRole.ADMIN);
  }

  /**
   * Check if user can manage settings
   */
  canManageSettings(organization: Organization): boolean {
    return this.hasMinimumRole(organization, OrganizationRole.ADMIN);
  }

  /**
   * Check if user can delete organization
   */
  canDeleteOrganization(organization: Organization): boolean {
    return organization.is_owner;
  }

  /**
   * Check if user can transfer ownership
   */
  canTransferOwnership(organization: Organization): boolean {
    return organization.is_owner;
  }

  /**
   * Format organization for display
   */
  formatOrganization(organization: Organization): {
    displayName: string;
    roleLabel: string;
    permissions: {
      canManageMembers: boolean;
      canManageSettings: boolean;
      canDelete: boolean;
      canTransferOwnership: boolean;
    };
  } {
    const roleLabels = {
      [OrganizationRole.OWNER]: 'Owner',
      [OrganizationRole.ADMIN]: 'Admin',
      [OrganizationRole.MEMBER]: 'Member',
      [OrganizationRole.VIEWER]: 'Viewer'
    };

    return {
      displayName: organization.name,
      roleLabel: roleLabels[organization.user_role as OrganizationRole] || 'Unknown',
      permissions: {
        canManageMembers: this.canManageMembers(organization),
        canManageSettings: this.canManageSettings(organization),
        canDelete: this.canDeleteOrganization(organization),
        canTransferOwnership: this.canTransferOwnership(organization)
      }
    };
  }

  /**
   * Get organization member count category
   */
  getMemberCountCategory(memberCount: number): 'small' | 'medium' | 'large' | 'enterprise' {
    if (memberCount <= 10) return 'small';
    if (memberCount <= 50) return 'medium';
    if (memberCount <= 200) return 'large';
    return 'enterprise';
  }

  /**
   * Generate organization invite URL
   */
  generateInviteUrl(baseUrl: string, token: string): string {
    return `${baseUrl}/accept-invitation?token=${token}`;
  }

  /**
   * Validate organization slug availability (client-side check)
   */
  isValidSlugFormat(slug: string): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!slug) {
      errors.push('Slug is required');
    } else {
      if (slug.length < 1 || slug.length > 100) {
        errors.push('Slug must be between 1 and 100 characters');
      }

      if (!/^[a-z0-9-]+$/.test(slug)) {
        errors.push('Slug can only contain lowercase letters, numbers, and hyphens');
      }

      if (slug.startsWith('-') || slug.endsWith('-')) {
        errors.push('Slug cannot start or end with a hyphen');
      }

      if (slug.includes('--')) {
        errors.push('Slug cannot contain consecutive hyphens');
      }

      // Reserved slugs
      const reserved = ['admin', 'api', 'www', 'app', 'mail', 'ftp', 'docs', 'help', 'support'];
      if (reserved.includes(slug)) {
        errors.push('This slug is reserved and cannot be used');
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}