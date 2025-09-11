import { HttpClient } from './utils/http';
import { OrganizationInfo, OrganizationMembership } from './types';

export interface CreateOrganizationRequest {
  name: string;
  slug?: string;
  description?: string;
  logoUrl?: string;
  metadata?: Record<string, any>;
}

export interface UpdateOrganizationRequest {
  name?: string;
  slug?: string;
  description?: string;
  logoUrl?: string;
  metadata?: Record<string, any>;
}

export interface InviteMemberRequest {
  email: string;
  role: string;
  permissions?: string[];
  sendEmail?: boolean;
}

export interface UpdateMemberRequest {
  role?: string;
  permissions?: string[];
}

export class OrganizationClient {
  private http: HttpClient;

  constructor(http: HttpClient) {
    this.http = http;
  }

  async createOrganization(data: CreateOrganizationRequest): Promise<OrganizationInfo> {
    return this.http.post<OrganizationInfo>('/api/v1/organizations', data);
  }

  async getOrganization(orgId: string): Promise<OrganizationInfo> {
    return this.http.get<OrganizationInfo>(`/api/v1/organizations/${orgId}`);
  }

  async updateOrganization(
    orgId: string,
    data: UpdateOrganizationRequest
  ): Promise<OrganizationInfo> {
    return this.http.patch<OrganizationInfo>(`/api/v1/organizations/${orgId}`, data);
  }

  async deleteOrganization(orgId: string): Promise<void> {
    await this.http.delete(`/api/v1/organizations/${orgId}`);
  }

  async listOrganizations(params?: {
    limit?: number;
    offset?: number;
    search?: string;
  }): Promise<{ organizations: OrganizationInfo[]; total: number }> {
    return this.http.get('/api/v1/organizations', { params: params as any });
  }

  async getUserOrganizations(): Promise<OrganizationMembership[]> {
    return this.http.get<OrganizationMembership[]>('/api/v1/users/organizations');
  }

  async getOrganizationMembers(
    orgId: string,
    params?: {
      limit?: number;
      offset?: number;
      role?: string;
      search?: string;
    }
  ): Promise<{
    members: Array<{
      id: string;
      userId: string;
      user: {
        id: string;
        email: string;
        firstName?: string;
        lastName?: string;
        profileImageUrl?: string;
      };
      role: string;
      permissions: string[];
      joinedAt: string;
    }>;
    total: number;
  }> {
    return this.http.get(`/api/v1/organizations/${orgId}/members`, {
      params: params as any,
    });
  }

  async inviteMember(
    orgId: string,
    data: InviteMemberRequest
  ): Promise<{
    invitation: {
      id: string;
      email: string;
      role: string;
      permissions: string[];
      status: 'pending' | 'accepted' | 'expired';
      expiresAt: string;
    };
  }> {
    return this.http.post(`/api/v1/organizations/${orgId}/invitations`, data);
  }

  async updateMember(
    orgId: string,
    userId: string,
    data: UpdateMemberRequest
  ): Promise<OrganizationMembership> {
    return this.http.patch<OrganizationMembership>(
      `/api/v1/organizations/${orgId}/members/${userId}`,
      data
    );
  }

  async removeMember(orgId: string, userId: string): Promise<void> {
    await this.http.delete(`/api/v1/organizations/${orgId}/members/${userId}`);
  }

  async leaveOrganization(orgId: string): Promise<void> {
    await this.http.post(`/api/v1/organizations/${orgId}/leave`);
  }

  async acceptInvitation(invitationId: string): Promise<OrganizationMembership> {
    return this.http.post<OrganizationMembership>(
      `/api/v1/organizations/invitations/${invitationId}/accept`
    );
  }

  async declineInvitation(invitationId: string): Promise<void> {
    await this.http.post(`/api/v1/organizations/invitations/${invitationId}/decline`);
  }

  async revokeInvitation(orgId: string, invitationId: string): Promise<void> {
    await this.http.delete(`/api/v1/organizations/${orgId}/invitations/${invitationId}`);
  }

  async listInvitations(
    orgId: string,
    params?: {
      limit?: number;
      offset?: number;
      status?: 'pending' | 'accepted' | 'expired';
    }
  ): Promise<{
    invitations: Array<{
      id: string;
      email: string;
      role: string;
      permissions: string[];
      status: 'pending' | 'accepted' | 'expired';
      createdAt: string;
      expiresAt: string;
    }>;
    total: number;
  }> {
    return this.http.get(`/api/v1/organizations/${orgId}/invitations`, {
      params: params as any,
    });
  }

  async getOrganizationRoles(orgId: string): Promise<
    Array<{
      id: string;
      name: string;
      description?: string;
      permissions: string[];
      isDefault: boolean;
      isSystem: boolean;
    }>
  > {
    return this.http.get(`/api/v1/organizations/${orgId}/roles`);
  }

  async createOrganizationRole(
    orgId: string,
    data: {
      name: string;
      description?: string;
      permissions: string[];
    }
  ): Promise<{
    id: string;
    name: string;
    description?: string;
    permissions: string[];
  }> {
    return this.http.post(`/api/v1/organizations/${orgId}/roles`, data);
  }

  async updateOrganizationRole(
    orgId: string,
    roleId: string,
    data: {
      name?: string;
      description?: string;
      permissions?: string[];
    }
  ): Promise<{
    id: string;
    name: string;
    description?: string;
    permissions: string[];
  }> {
    return this.http.patch(`/api/v1/organizations/${orgId}/roles/${roleId}`, data);
  }

  async deleteOrganizationRole(orgId: string, roleId: string): Promise<void> {
    await this.http.delete(`/api/v1/organizations/${orgId}/roles/${roleId}`);
  }

  async getOrganizationPermissions(orgId: string): Promise<
    Array<{
      id: string;
      name: string;
      description?: string;
      category: string;
    }>
  > {
    return this.http.get(`/api/v1/organizations/${orgId}/permissions`);
  }

  async transferOwnership(orgId: string, newOwnerId: string): Promise<void> {
    await this.http.post(`/api/v1/organizations/${orgId}/transfer`, {
      newOwnerId,
    });
  }

  async getOrganizationSettings(orgId: string): Promise<Record<string, any>> {
    return this.http.get(`/api/v1/organizations/${orgId}/settings`);
  }

  async updateOrganizationSettings(
    orgId: string,
    settings: Record<string, any>
  ): Promise<Record<string, any>> {
    return this.http.patch(`/api/v1/organizations/${orgId}/settings`, settings);
  }

  async getOrganizationBilling(orgId: string): Promise<{
    plan: string;
    status: string;
    currentPeriodEnd?: string;
    seats: number;
    usedSeats: number;
  }> {
    return this.http.get(`/api/v1/organizations/${orgId}/billing`);
  }

  async getOrganizationUsage(
    orgId: string,
    params?: {
      startDate?: string;
      endDate?: string;
      metric?: string;
    }
  ): Promise<{
    usage: Array<{
      date: string;
      metric: string;
      value: number;
    }>;
    summary: Record<string, number>;
  }> {
    return this.http.get(`/api/v1/organizations/${orgId}/usage`, {
      params: params as any,
    });
  }
}