/**
 * Session management module
 */

import type { HttpClient } from './http-client';
import type { Session, SessionListParams, PaginatedResponse, UUID } from './types';

/**
 * Sessions module for managing user sessions
 */
export class Sessions {
  constructor(private httpClient: HttpClient) {}

  /**
   * Get the current session
   */
  async getCurrentSession(): Promise<Session> {
    const response = await this.httpClient.request<{ session: Session }>({
      method: 'GET',
      url: '/sessions/current'
    });
    return response.data.session;
  }

  /**
   * List all sessions for the current user
   */
  async listSessions(params?: SessionListParams): Promise<PaginatedResponse<Session>> {
    const response = await this.httpClient.request<PaginatedResponse<Session>>({
      method: 'GET',
      url: '/sessions',
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
      url: `/sessions/${sessionId}`
    });
    return response.data.session;
  }

  /**
   * Revoke a specific session
   */
  async revokeSession(sessionId: UUID): Promise<void> {
    await this.httpClient.request({
      method: 'DELETE',
      url: `/sessions/${sessionId}`
    });
  }

  /**
   * Revoke all sessions except the current one
   */
  async revokeAllSessions(): Promise<{ revokedCount: number }> {
    const response = await this.httpClient.request<{ revokedCount: number }>({
      method: 'POST',
      url: '/sessions/revoke-all'
    });
    return response.data;
  }

  /**
   * Refresh the current session
   */
  async refreshSession(): Promise<Session> {
    const response = await this.httpClient.request<{ session: Session }>({
      method: 'POST',
      url: '/sessions/refresh'
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