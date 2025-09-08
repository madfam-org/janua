/**
 * Plinto JavaScript/TypeScript SDK
 */

import { z } from 'zod'
import { verifyToken, type JWTPayload } from './jwt'
import { JWKSCache } from './jwks'
import type {
  PlintoConfig,
  CreateIdentityData,
  CreateSessionData,
  Identity,
  Session,
  Organization,
  TokenPair,
  PlintoError
} from './types'

export * from './types'
export { verifyToken } from './jwt'

/**
 * Main Plinto SDK client
 */
export class PlintoClient {
  private config: PlintoConfig
  private jwksCache: JWKSCache | null = null

  constructor(config: PlintoConfig) {
    this.config = {
      baseUrl: 'https://plinto.dev',
      ...config
    }

    // Initialize JWKS cache if verification is needed
    if (config.enableLocalVerification) {
      this.jwksCache = new JWKSCache(
        config.jwksUrl || `${this.config.baseUrl}/.well-known/jwks.json`
      )
    }
  }

  /**
   * Identity management
   */
  identities = {
    /**
     * Create a new identity
     */
    create: async (data: CreateIdentityData): Promise<Identity> => {
      return this.request('/api/v1/identities', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Get identity by ID
     */
    get: async (id: string): Promise<Identity> => {
      return this.request(`/api/v1/identities/${id}`)
    },

    /**
     * Update identity
     */
    update: async (id: string, data: Partial<Identity>): Promise<Identity> => {
      return this.request(`/api/v1/identities/${id}`, {
        method: 'PATCH',
        body: data
      })
    },

    /**
     * Delete identity
     */
    delete: async (id: string): Promise<void> => {
      return this.request(`/api/v1/identities/${id}`, {
        method: 'DELETE'
      })
    },

    /**
     * List identities
     */
    list: async (params?: {
      limit?: number
      cursor?: string
      email?: string
    }): Promise<{ data: Identity[]; nextCursor?: string }> => {
      const query = new URLSearchParams(params as any).toString()
      return this.request(`/api/v1/identities${query ? `?${query}` : ''}`)
    }
  }

  /**
   * Session management
   */
  sessions = {
    /**
     * Create a new session (login)
     */
    create: async (data: CreateSessionData): Promise<Session> => {
      return this.request('/api/v1/sessions', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Verify session token
     */
    verify: async (token: string): Promise<JWTPayload> => {
      // Try local verification first if enabled
      if (this.jwksCache) {
        try {
          const jwks = await this.jwksCache.get()
          if (jwks) {
            return await verifyToken(token, jwks, {
              audience: this.config.audience || 'plinto.dev',
              issuer: this.config.issuer || 'https://plinto.dev'
            })
          }
        } catch (error) {
          console.warn('Local verification failed, falling back to API:', error)
        }
      }

      // Fall back to API verification
      return this.request('/api/v1/sessions/verify', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
    },

    /**
     * Refresh session tokens
     */
    refresh: async (refreshToken: string): Promise<TokenPair> => {
      return this.request('/api/v1/sessions/refresh', {
        method: 'POST',
        body: { refreshToken }
      })
    },

    /**
     * Revoke session
     */
    revoke: async (sessionId: string): Promise<void> => {
      return this.request(`/api/v1/sessions/${sessionId}`, {
        method: 'DELETE'
      })
    },

    /**
     * Get current session
     */
    current: async (token: string): Promise<Session> => {
      return this.request('/api/v1/sessions/current', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
    }
  }

  /**
   * Organization management
   */
  organizations = {
    /**
     * Create organization
     */
    create: async (data: {
      name: string
      slug: string
      description?: string
    }): Promise<Organization> => {
      return this.request('/api/v1/organizations', {
        method: 'POST',
        body: data
      })
    },

    /**
     * Get organization
     */
    get: async (id: string): Promise<Organization> => {
      return this.request(`/api/v1/organizations/${id}`)
    },

    /**
     * List organizations
     */
    list: async (params?: {
      limit?: number
      cursor?: string
    }): Promise<{ data: Organization[]; nextCursor?: string }> => {
      const query = new URLSearchParams(params as any).toString()
      return this.request(`/api/v1/organizations${query ? `?${query}` : ''}`)
    },

    /**
     * Add member to organization
     */
    addMember: async (
      orgId: string,
      data: {
        email: string
        role: string
      }
    ): Promise<void> => {
      return this.request(`/api/v1/organizations/${orgId}/members`, {
        method: 'POST',
        body: data
      })
    },

    /**
     * Remove member from organization
     */
    removeMember: async (orgId: string, memberId: string): Promise<void> => {
      return this.request(`/api/v1/organizations/${orgId}/members/${memberId}`, {
        method: 'DELETE'
      })
    }
  }

  /**
   * Passkey management
   */
  passkeys = {
    /**
     * Begin passkey registration
     */
    beginRegistration: async (identityId: string): Promise<any> => {
      return this.request('/api/v1/passkeys/registration/begin', {
        method: 'POST',
        body: { identityId }
      })
    },

    /**
     * Complete passkey registration
     */
    completeRegistration: async (
      identityId: string,
      credential: any
    ): Promise<any> => {
      return this.request('/api/v1/passkeys/registration/complete', {
        method: 'POST',
        body: { identityId, credential }
      })
    },

    /**
     * Begin passkey authentication
     */
    beginAuthentication: async (): Promise<any> => {
      return this.request('/api/v1/passkeys/authentication/begin', {
        method: 'POST'
      })
    },

    /**
     * Complete passkey authentication
     */
    completeAuthentication: async (credential: any): Promise<Session> => {
      return this.request('/api/v1/passkeys/authentication/complete', {
        method: 'POST',
        body: { credential }
      })
    }
  }

  /**
   * Policy evaluation
   */
  policies = {
    /**
     * Evaluate policy
     */
    evaluate: async (data: {
      subject: string
      action: string
      resource: string
      context?: Record<string, any>
    }): Promise<{
      allowed: boolean
      reasons: string[]
    }> => {
      return this.request('/api/v1/policies/evaluate', {
        method: 'POST',
        body: data
      })
    }
  }

  /**
   * Make authenticated request
   */
  private async request<T = any>(
    path: string,
    options: Omit<RequestInit, 'body'> & { body?: any } = {}
  ): Promise<T> {
    const url = `${this.config.baseUrl}${path}`
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...options.headers
    }

    // Add API key if provided
    if (this.config.apiKey) {
      headers['Authorization'] = `Bearer ${this.config.apiKey}`
    }

    // Add tenant ID if provided
    if (this.config.tenantId) {
      headers['X-Plinto-Tenant'] = this.config.tenantId
    }

    const response = await fetch(url, {
      ...options,
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    })

    // Handle response
    if (!response.ok) {
      const error = await response.json().catch(() => ({
        error: {
          code: 'unknown_error',
          message: `HTTP ${response.status}: ${response.statusText}`
        }
      }))
      
      throw new PlintoAPIError(
        error.error?.message || 'Request failed',
        error.error?.code || 'unknown_error',
        response.status
      )
    }

    // Handle empty responses
    if (response.status === 204) {
      return undefined as T
    }

    return response.json()
  }
}

/**
 * Plinto API Error
 */
export class PlintoAPIError extends Error implements PlintoError {
  constructor(
    message: string,
    public code: string,
    public status: number
  ) {
    super(message)
    this.name = 'PlintoAPIError'
  }
}

/**
 * Create a Plinto client instance
 */
export function createClient(config: PlintoConfig): PlintoClient {
  return new PlintoClient(config)
}