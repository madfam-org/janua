/**
 * Core authentication service for the Janua TypeScript SDK
 *
 * Handles fundamental auth operations: signUp, signIn, signOut, token refresh, user profile
 */

import type { HttpClient } from '../http-client';
import type {
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  AuthResponse,
  AuthApiResponse,
  TokenResponse,
  User,
  UserUpdateRequest
} from '../types';
import { AuthenticationError, ValidationError } from '../errors';
import { ValidationUtils, TokenManager } from '../utils';

/**
 * Core authentication operations
 */
export class CoreAuthService {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void,
    private onSignOut?: () => void
  ) {}

  /**
   * Sign up a new user
   */
  async signUp(request: SignUpRequest): Promise<AuthResponse> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const passwordValidation = ValidationUtils.validatePassword(request.password);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    if (request.username && !ValidationUtils.isValidUsername(request.username)) {
      throw new ValidationError('Invalid username format');
    }

    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/register', request);

    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + (response.data.expires_in * 1000)
      });
    }

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
   * Sign in user with email/username and password
   */
  async signIn(request: SignInRequest): Promise<AuthResponse> {
    if (!request.email && !request.username) {
      throw new ValidationError('Either email or username must be provided');
    }

    if (request.email && !ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    if (request.username && !ValidationUtils.isValidUsername(request.username)) {
      throw new ValidationError('Invalid username format');
    }

    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/login', request);

    // Handle MFA requirement
    if ('requires_mfa' in response.data) {
      return response.data as unknown as AuthResponse;
    }

    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + (response.data.expires_in * 1000)
      });
    }

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
   * Sign out current user
   */
  async signOut(): Promise<void> {
    try {
      const refreshToken = await this.tokenManager.getRefreshToken();
      await this.http.post('/api/v1/auth/logout', { refresh_token: refreshToken });
    } catch {
      // Continue with sign out even if API call fails
    } finally {
      await this.tokenManager.clearTokens();
      if (this.onSignOut) {
        this.onSignOut();
      }
    }
  }

  /**
   * Refresh access token
   */
  async refreshToken(request?: RefreshTokenRequest): Promise<TokenResponse> {
    if (!request) {
      const refreshToken = await this.tokenManager.getRefreshToken();
      if (!refreshToken) {
        throw new AuthenticationError('No refresh token available');
      }
      request = { refresh_token: refreshToken };
    }

    const response = await this.http.post<TokenResponse>('/api/v1/auth/refresh', request, {
      skipAuth: true
    });

    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + ((response.data as TokenResponse & { expires_in: number }).expires_in * 1000)
      });
    }

    return {
      access_token: response.data.access_token,
      refresh_token: response.data.refresh_token,
      expires_in: response.data.expires_in,
      token_type: response.data.token_type
    };
  }

  /**
   * Get current user information
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await this.http.get<User>('/api/v1/auth/me');
      return response.data;
    } catch (error) {
      if (error instanceof AuthenticationError) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Update user profile
   */
  async updateProfile(updates: UserUpdateRequest): Promise<User> {
    const response = await this.http.patch<User>('/api/v1/auth/profile', updates);
    return response.data;
  }
}
