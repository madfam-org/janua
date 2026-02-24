/**
 * Admin API Client
 *
 * Fetches real data from the Janua API admin endpoints
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

export interface AdminStats {
  total_users: number
  active_users: number
  suspended_users: number
  deleted_users: number
  total_organizations: number
  total_sessions: number
  active_sessions: number
  mfa_enabled_users: number
  oauth_accounts: number
  passkeys_registered: number
  users_last_24h: number
  sessions_last_24h: number
}

export interface SystemHealth {
  status: string
  database: string
  cache: string
  storage: string
  email: string
  uptime: number
  version: string
  environment: string
}

export interface AdminUser {
  id: string
  email: string
  email_verified: boolean
  username: string | null
  first_name: string | null
  last_name: string | null
  status: string
  mfa_enabled: boolean
  is_admin: boolean
  organizations_count: number
  sessions_count: number
  oauth_providers: string[]
  passkeys_count: number
  created_at: string
  updated_at: string
  last_sign_in_at: string | null
}

export interface AdminOrganization {
  id: string
  name: string
  slug: string
  owner_id: string
  owner_email: string
  billing_plan: string
  billing_email: string | null
  members_count: number
  created_at: string
  updated_at: string
}

export interface ActivityLog {
  id: string
  user_id: string
  user_email: string
  action: string
  details: Record<string, unknown>
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

class AdminAPI {
  private getAuthHeaders(): HeadersInit {
    // Get token from localStorage (set by auth flow)
    const token = typeof window !== 'undefined' ? localStorage.getItem('janua_access_token') : null
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    }
  }

  async getStats(): Promise<AdminStats> {
    const response = await fetch(`${API_URL}/api/v1/admin/stats`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`)
    }

    return response.json()
  }

  async getHealth(): Promise<SystemHealth> {
    const response = await fetch(`${API_URL}/api/v1/admin/health`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch health: ${response.statusText}`)
    }

    return response.json()
  }

  async getUsers(page: number = 1, limit: number = 20): Promise<AdminUser[] | { items: AdminUser[]; total: number; page: number; pages: number }> {
    const response = await fetch(`${API_URL}/api/v1/admin/users?page=${page}&limit=${limit}`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch users: ${response.statusText}`)
    }

    return response.json()
  }

  async getOrganizations(page: number = 1, limit: number = 20): Promise<AdminOrganization[]> {
    const response = await fetch(`${API_URL}/api/v1/admin/organizations?page=${page}&limit=${limit}`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch organizations: ${response.statusText}`)
    }

    return response.json()
  }

  async getActivityLogs(limit: number = 50): Promise<ActivityLog[]> {
    const response = await fetch(`${API_URL}/api/v1/admin/activity-logs?limit=${limit}`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch activity logs: ${response.statusText}`)
    }

    return response.json()
  }

  async updateUserStatus(userId: string, status: string): Promise<void> {
    const response = await fetch(`${API_URL}/api/v1/admin/users/${userId}`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ status }),
    })

    if (!response.ok) {
      throw new Error(`Failed to update user: ${response.statusText}`)
    }
  }

  async deleteUser(userId: string): Promise<void> {
    const response = await fetch(`${API_URL}/api/v1/admin/users/${userId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to delete user: ${response.statusText}`)
    }
  }

  async revokeAllSessions(): Promise<void> {
    const response = await fetch(`${API_URL}/api/v1/admin/sessions/revoke-all`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error(`Failed to revoke sessions: ${response.statusText}`)
    }
  }

  async setMaintenanceMode(enabled: boolean): Promise<void> {
    const response = await fetch(`${API_URL}/api/v1/admin/maintenance-mode`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ enabled }),
    })

    if (!response.ok) {
      throw new Error(`Failed to set maintenance mode: ${response.statusText}`)
    }
  }
}

export const adminAPI = new AdminAPI()
