/**
 * OAuth authentication service for the Janua TypeScript SDK
 */

import type { HttpClient } from '../http-client';
import type {
  AuthResponse,
  AuthApiResponse,
  User,
  OAuthProvider,
  OAuthProvidersResponse,
  LinkedAccountsResponse
} from '../types';
import type { TokenManager } from '../utils';

/**
 * OAuth authentication operations
 */
export class OAuthService {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void
  ) {}

  /**
   * Get available OAuth providers
   */
  async getProviders(): Promise<Array<{ provider?: string; name: string; enabled: boolean }>> {
    const response = await this.http.get<OAuthProvidersResponse>('/api/v1/auth/oauth/providers', {
      skipAuth: true
    });
    return response.data.providers;
  }

  /**
   * Sign in with OAuth provider (simple API)
   */
  async signIn(params: { provider: string; redirect_uri: string }): Promise<{
    authorization_url: string;
  }> {
    const response = await this.http.get('/api/v1/auth/oauth/authorize', {
      params
    });
    return response.data;
  }

  /**
   * Initiate OAuth authorization flow
   */
  async initiate(
    provider: OAuthProvider,
    options?: {
      redirect_uri?: string;
      redirect_to?: string;
      scopes?: string[];
    }
  ): Promise<{
    authorization_url: string;
    state: string;
    provider: string;
  }> {
    const params: Record<string, string> = {};

    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }
    if (options?.redirect_to) {
      params.redirect_to = options.redirect_to;
    }
    if (options?.scopes) {
      params.scopes = options.scopes.join(',');
    }

    const response = await this.http.post<{ authorization_url: string; state: string; provider: string }>(
      `/api/v1/auth/oauth/authorize/${provider}`,
      null,
      { params, skipAuth: true }
    );
    return response.data;
  }

  /**
   * Handle OAuth callback
   */
  async handleCallback(code: string, state: string): Promise<AuthResponse> {
    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/oauth/callback', {
      code,
      state
    }, { skipAuth: true });

    // Store tokens
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + (response.data.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return {
      user: response.data.user,
      tokens: {
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_in: response.data.expires_in,
        token_type: response.data.token_type
      }
    };
  }

  /**
   * Handle OAuth callback with provider (for advanced use)
   */
  async handleCallbackWithProvider(
    provider: OAuthProvider,
    code: string,
    state: string
  ): Promise<{
    access_token?: string;
    refresh_token?: string;
    token_type?: string;
    expires_in?: number;
    user?: User;
    is_new_user?: boolean;
    status?: string;
    redirect_url?: string;
  }> {
    const response = await this.http.get(`/api/v1/auth/oauth/callback/${provider}`, {
      params: { code, state },
      skipAuth: true
    });

    // Store tokens if present
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + (response.data.expires_in * 1000)
      });
    }

    // Call onSignIn callback if user is present
    if (this.onSignIn && response.data.user) {
      this.onSignIn({ user: response.data.user });
    }

    return response.data;
  }

  /**
   * Link OAuth account to current user
   */
  async linkAccount(
    provider: OAuthProvider,
    options?: { redirect_uri?: string }
  ): Promise<{
    authorization_url: string;
    state: string;
    provider: string;
    action: string;
  }> {
    const params: Record<string, string> = {};

    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }

    const response = await this.http.post<{
      authorization_url: string;
      state: string;
      provider: string;
      action: string;
    }>(`/api/v1/auth/oauth/link/${provider}`, null, { params });
    return response.data;
  }

  /**
   * Unlink OAuth account from current user
   */
  async unlinkAccount(provider: OAuthProvider): Promise<{
    message: string;
    provider: string;
  }> {
    const response = await this.http.delete<{ message: string; provider: string }>(
      `/api/v1/auth/oauth/unlink/${provider}`
    );
    return response.data;
  }

  /**
   * Get linked OAuth accounts for current user
   */
  async getLinkedAccounts(): Promise<LinkedAccountsResponse> {
    const response = await this.http.get<LinkedAccountsResponse>('/api/v1/auth/oauth/accounts');
    return response.data;
  }
}
