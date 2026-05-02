/**
 * Session management module
 */

import type { HttpClient } from './http-client';
import type { Session, SessionListParams, PaginatedResponse, UUID } from './types';

/**
 * Sessions module for managing user sessions
 *
 * NOTE: All paths must include the `/api/v1` prefix to match the FastAPI
 * router mount point (apps/api/app/main.py: include_router(..., prefix="/api/v1")).
 * Prior versions called `/sessions/...` directly which 404'd in production
 * because baseURL was `https://api.janua.dev` (the dashboard's Sessions tab
 * displayed "Failed to Load Sessions — Request failed with status code 404").
 */
export class Sessions {
  constructor(private httpClient: HttpClient) {}

  /**
   * Get the current session
   */
  async getCurrentSession(): Promise<Session> {
    const response = await this.httpClient.request<{ session: Session }>({
      method: 'GET',
      url: '/api/v1/sessions/current'
    });
    return response.data.session;
  }

  /**
   * List all sessions for the current user
   */
  async listSessions(params?: SessionListParams): Promise<PaginatedResponse<Session>> {
    const response = await this.httpClient.request<PaginatedResponse<Session>>({
      method: 'GET',
      url: '/api/v1/sessions',
      params
    });
    return response.data;
  }

  /**
   * Get a specific session by ID
   */
  async getSession(sessionId: UUID): Promise<Session> {
    const response = await this.httpClient.request<{ session: Session }>({
      method: 'GET',
      url: `/api/v1/sessions/${sessionId}`
    });
    return response.data.session;
  }

  /**
   * Revoke a specific session
   */
  async revokeSession(sessionId: UUID): Promise<void> {
    await this.httpClient.request({
      method: 'DELETE',
      url: `/api/v1/sessions/${sessionId}`
    });
  }

  /**
   * Revoke all sessions except the current one
   */
  async revokeAllSessions(): Promise<{ revokedCount: number }> {
    const response = await this.httpClient.request<{ revokedCount: number }>({
      method: 'POST',
      url: '/api/v1/sessions/revoke-all'
    });
    return response.data;
  }

  /**
   * Refresh the current session
   */
  async refreshSession(): Promise<Session> {
    const response = await this.httpClient.request<{ session: Session }>({
      method: 'POST',
      url: '/api/v1/sessions/refresh'
    });
    return response.data.session;
  }

  /**
   * Alias for refreshSession for backward compatibility
   */
  async refresh(): Promise<Session> {
    return this.refreshSession();
  }

  /**
   * Verify if a session is valid
   */
  async verifySession(sessionId: UUID): Promise<{ valid: boolean; session?: Session }> {
    try {
      const session = await this.getSession(sessionId);
      return { valid: !session.revoked, session };
    } catch {
      return { valid: false };
    }
  }
}
