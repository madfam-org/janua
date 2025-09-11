/**
 * Admin operations module for the Plinto TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  AdminStatsResponse,
  SystemHealthResponse,
  User,
  UserStatus,
  Organization,
  PaginatedResponse,
  UserListParams,
  OrganizationListParams
} from './types';
import { ValidationError, PermissionError } from './errors';
import { ValidationUtils } from './utils';

/**
 * Administrative operations (admin only)
 */
export class Admin {
  constructor(private http: HttpClient) {}

  /**
   * Get system statistics
   */
  async getStats(): Promise<AdminStatsResponse> {
    const response = await this.http.get<AdminStatsResponse>('/api/v1/admin/stats');
    return response.data;
  }

  /**
   * Get system health status
   */
  async getSystemHealth(): Promise<SystemHealthResponse> {
    const response = await this.http.get<SystemHealthResponse>('/api/v1/admin/health');
    return response.data;
  }

  /**
   * Get system configuration
   */
  async getSystemConfig(): Promise<{
    environment: string;
    app_name: string;
    domain: string;
    version: string;
    features: {
      mfa_enabled: boolean;
      passkeys_enabled: boolean;
      oauth_providers: string[];
      magic_links_enabled: boolean;
      organizations_enabled: boolean;
    };
    limits: {
      max_sessions_per_user: number;
      session_timeout_minutes: number;
      refresh_token_days: number;
      password_reset_expire_minutes: number;
      magic_link_expire_minutes: number;
      invitation_expire_days: number;
    };
  }> {
    const response = await this.http.get('/api/v1/admin/config');
    return response.data;
  }

  // User Management

  /**
   * List all users (admin only)
   */
  async listAllUsers(params?: UserListParams & {
    mfa_enabled?: boolean;
    is_admin?: boolean;
  }): Promise<PaginatedResponse<{
    id: string;
    email: string;
    email_verified: boolean;
    username?: string;
    first_name?: string;
    last_name?: string;
    status: string;
    mfa_enabled: boolean;
    is_admin: boolean;
    organizations_count: number;
    sessions_count: number;
    oauth_providers: string[];
    passkeys_count: number;
    created_at: string;
    updated_at: string;
    last_sign_in_at?: string;
  }>> {
    // Validate pagination parameters
    if (params?.page && params.page < 1) {
      throw new ValidationError('Page must be greater than 0');
    }

    if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
      throw new ValidationError('Per page must be between 1 and 100');
    }

    const response = await this.http.get<Array<{
      id: string;
      email: string;
      email_verified: boolean;
      username?: string;
      first_name?: string;
      last_name?: string;
      status: string;
      mfa_enabled: boolean;
      is_admin: boolean;
      organizations_count: number;
      sessions_count: number;
      oauth_providers: string[];
      passkeys_count: number;
      created_at: string;
      updated_at: string;
      last_sign_in_at?: string;
    }>>('/api/v1/admin/users', {
      params
    });

    // Since the API returns an array, we need to simulate pagination
    const users = response.data;
    const page = params?.page || 1;
    const perPage = params?.per_page || 20;

    return {
      data: users,
      total: users.length,
      page,
      per_page: perPage,
      total_pages: Math.ceil(users.length / perPage)
    };
  }

  /**
   * Update user as admin
   */
  async updateUser(
    userId: string,
    updates: {
      status?: UserStatus;
      is_admin?: boolean;
      email_verified?: boolean;
    }
  ): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(userId)) {
      throw new ValidationError('Invalid user ID format');
    }

    // Validate status if provided
    if (updates.status && !Object.values(UserStatus).includes(updates.status)) {
      throw new ValidationError('Invalid user status');
    }

    const response = await this.http.patch<{ message: string }>(`/api/v1/admin/users/${userId}`, updates);
    return response.data;
  }

  /**
   * Delete user as admin
   */
  async deleteUser(userId: string, permanent = false): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(userId)) {
      throw new ValidationError('Invalid user ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/admin/users/${userId}`, {
      params: { permanent }
    });
    return response.data;
  }

  // Organization Management

  /**
   * List all organizations (admin only)
   */
  async listAllOrganizations(params?: OrganizationListParams): Promise<PaginatedResponse<{
    id: string;
    name: string;
    slug: string;
    owner_id: string;
    owner_email: string;
    billing_plan: string;
    billing_email?: string;
    members_count: number;
    created_at: string;
    updated_at: string;
  }>> {
    // Validate pagination parameters
    if (params?.page && params.page < 1) {
      throw new ValidationError('Page must be greater than 0');
    }

    if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
      throw new ValidationError('Per page must be between 1 and 100');
    }

    const response = await this.http.get<Array<{
      id: string;
      name: string;
      slug: string;
      owner_id: string;
      owner_email: string;
      billing_plan: string;
      billing_email?: string;
      members_count: number;
      created_at: string;
      updated_at: string;
    }>>('/api/v1/admin/organizations', {
      params
    });

    // Since the API returns an array, we need to simulate pagination
    const organizations = response.data;
    const page = params?.page || 1;
    const perPage = params?.per_page || 20;

    return {
      data: organizations,
      total: organizations.length,
      page,
      per_page: perPage,
      total_pages: Math.ceil(organizations.length / perPage)
    };
  }

  /**
   * Delete organization as admin
   */
  async deleteOrganization(organizationId: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUUID(organizationId)) {
      throw new ValidationError('Invalid organization ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/admin/organizations/${organizationId}`);
    return response.data;
  }

  // Activity Logs

  /**
   * Get activity logs
   */
  async getActivityLogs(options?: {
    page?: number;
    per_page?: number;
    user_id?: string;
    action?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<PaginatedResponse<{
    id: string;
    user_id: string;
    user_email: string;
    action: string;
    details: Record<string, any>;
    ip_address?: string;
    user_agent?: string;
    created_at: string;
  }>> {
    // Validate parameters
    if (options?.page && options.page < 1) {
      throw new ValidationError('Page must be greater than 0');
    }

    if (options?.per_page && (options.per_page < 1 || options.per_page > 200)) {
      throw new ValidationError('Per page must be between 1 and 200');
    }

    if (options?.user_id && !ValidationUtils.isValidUUID(options.user_id)) {
      throw new ValidationError('Invalid user ID format');
    }

    if (options?.start_date && isNaN(Date.parse(options.start_date))) {
      throw new ValidationError('Invalid start date format');
    }

    if (options?.end_date && isNaN(Date.parse(options.end_date))) {
      throw new ValidationError('Invalid end date format');
    }

    const response = await this.http.get<Array<{
      id: string;
      user_id: string;
      user_email: string;
      action: string;
      details: Record<string, any>;
      ip_address?: string;
      user_agent?: string;
      created_at: string;
    }>>('/api/v1/admin/activity-logs', {
      params: options
    });

    // Since the API returns an array, we need to simulate pagination
    const logs = response.data;
    const page = options?.page || 1;
    const perPage = options?.per_page || 50;

    return {
      data: logs,
      total: logs.length,
      page,
      per_page: perPage,
      total_pages: Math.ceil(logs.length / perPage)
    };
  }

  // Session Management

  /**
   * Revoke all sessions (optionally for specific user)
   */
  async revokeAllSessions(userId?: string): Promise<{ message: string }> {
    if (userId && !ValidationUtils.isValidUUID(userId)) {
      throw new ValidationError('Invalid user ID format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/admin/sessions/revoke-all', {
      user_id: userId
    });
    return response.data;
  }

  /**
   * Toggle maintenance mode
   */
  async toggleMaintenanceMode(
    enabled: boolean,
    message?: string
  ): Promise<{
    maintenance_mode: boolean;
    message: string;
    note: string;
  }> {
    const response = await this.http.post<{
      maintenance_mode: boolean;
      message: string;
      note: string;
    }>('/api/v1/admin/maintenance-mode', {
      enabled,
      message
    });
    return response.data;
  }

  // Helper Methods

  /**
   * Format user status for display
   */
  formatUserStatus(status: string): {
    label: string;
    color: 'green' | 'yellow' | 'red' | 'gray';
    description: string;
  } {
    switch (status) {
      case UserStatus.ACTIVE:
        return {
          label: 'Active',
          color: 'green',
          description: 'User account is active and can sign in'
        };
      case UserStatus.SUSPENDED:
        return {
          label: 'Suspended',
          color: 'yellow',
          description: 'User account is suspended and cannot sign in'
        };
      case UserStatus.DELETED:
        return {
          label: 'Deleted',
          color: 'red',
          description: 'User account has been deleted'
        };
      default:
        return {
          label: 'Unknown',
          color: 'gray',
          description: 'Unknown user status'
        };
    }
  }

  /**
   * Calculate system health score
   */
  calculateHealthScore(health: SystemHealthResponse): {
    score: number;
    status: 'healthy' | 'degraded' | 'unhealthy';
    issues: string[];
  } {
    const services = ['database', 'cache', 'storage', 'email'];
    const healthyServices = services.filter(service => health[service as keyof SystemHealthResponse] === 'healthy');
    const score = (healthyServices.length / services.length) * 100;

    const issues: string[] = [];
    services.forEach(service => {
      const status = health[service as keyof SystemHealthResponse];
      if (status !== 'healthy') {
        issues.push(`${service} is ${status}`);
      }
    });

    let status: 'healthy' | 'degraded' | 'unhealthy';
    if (score === 100) status = 'healthy';
    else if (score >= 75) status = 'degraded';
    else status = 'unhealthy';

    return { score, status, issues };
  }

  /**
   * Format statistics for dashboard
   */
  formatStats(stats: AdminStatsResponse): {
    userGrowth: {
      total: number;
      active: number;
      recent: number;
      growthRate: number;
    };
    security: {
      mfaAdoption: number;
      oauthAccounts: number;
      passkeysRegistered: number;
    };
    activity: {
      totalSessions: number;
      activeSessions: number;
      recentSessions: number;
    };
  } {
    const mfaAdoption = stats.total_users > 0 ? (stats.mfa_enabled_users / stats.total_users) * 100 : 0;

    return {
      userGrowth: {
        total: stats.total_users,
        active: stats.active_users,
        recent: stats.users_last_24h,
        growthRate: stats.total_users > 0 ? (stats.users_last_24h / stats.total_users) * 100 : 0
      },
      security: {
        mfaAdoption: Math.round(mfaAdoption * 100) / 100,
        oauthAccounts: stats.oauth_accounts,
        passkeysRegistered: stats.passkeys_registered
      },
      activity: {
        totalSessions: stats.total_sessions,
        activeSessions: stats.active_sessions,
        recentSessions: stats.sessions_last_24h
      }
    };
  }

  /**
   * Get organization size category
   */
  getOrganizationSizeCategory(memberCount: number): {
    category: 'startup' | 'small' | 'medium' | 'large' | 'enterprise';
    label: string;
    description: string;
  } {
    if (memberCount <= 5) {
      return {
        category: 'startup',
        label: 'Startup',
        description: '1-5 members'
      };
    } else if (memberCount <= 25) {
      return {
        category: 'small',
        label: 'Small',
        description: '6-25 members'
      };
    } else if (memberCount <= 100) {
      return {
        category: 'medium',
        label: 'Medium',
        description: '26-100 members'
      };
    } else if (memberCount <= 500) {
      return {
        category: 'large',
        label: 'Large',
        description: '101-500 members'
      };
    } else {
      return {
        category: 'enterprise',
        label: 'Enterprise',
        description: '500+ members'
      };
    }
  }

  /**
   * Validate admin permissions
   */
  private validateAdminPermissions(): void {
    // This would typically be handled by the HTTP client middleware
    // but we can add an explicit check here for better error messages
  }
}