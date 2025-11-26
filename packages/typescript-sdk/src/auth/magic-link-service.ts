/**
 * Magic Link Service
 * Handles passwordless authentication via magic links
 */

import type { HttpClient } from '../http-client';
import type { MagicLinkRequest, AuthResponse, User } from '../types';
import { ValidationError, AuthenticationError } from '../errors';
import { ValidationUtils, TokenManager } from '../utils';

export class MagicLinkService {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void
  ) {}

  /**
   * Send magic link to email
   */
  async sendMagicLink(request: MagicLinkRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/magic-link',
      request,
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Resend magic link
   */
  async resendMagicLink(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/magic-link/resend',
      { email },
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Verify magic link token and sign in
   */
  async verifyMagicLink(token: string): Promise<AuthResponse> {
    const response = await this.http.post<{
      user: User;
      tokens?: {
        access_token: string;
        refresh_token: string;
        expires_in: number;
        token_type: 'bearer';
      };
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
      token_type?: 'bearer';
    }>('/api/v1/auth/magic-link/verify', { token }, { skipAuth: true });

    // Handle both response formats
    if (response.data.tokens && response.data.tokens.access_token && response.data.tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.tokens.access_token,
        refresh_token: response.data.tokens.refresh_token,
        expires_at: Date.now() + (response.data.tokens.expires_in * 1000)
      });

      if (this.onSignIn) {
        this.onSignIn({ user: response.data.user });
      }

      return {
        user: response.data.user,
        tokens: response.data.tokens
      };
    }

    // Legacy format
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + ((response.data.expires_in || 3600) * 1000)
      });

      if (this.onSignIn) {
        this.onSignIn({ user: response.data.user });
      }

      return {
        user: response.data.user,
        tokens: {
          access_token: response.data.access_token,
          refresh_token: response.data.refresh_token,
          expires_in: response.data.expires_in || 3600,
          token_type: response.data.token_type || 'bearer'
        }
      };
    }

    throw new AuthenticationError('Invalid magic link verification response');
  }
}
