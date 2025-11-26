/**
 * Authentication module for the Janua TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  ForgotPasswordRequest,
  MagicLinkRequest,
  AuthResponse,
  AuthApiResponse,
  TokenResponse,
  User,
  UserUpdateRequest,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  OAuthProvider,
  OAuthProvidersResponse,
  LinkedAccountsResponse,
  Passkey,
  PublicKeyCredentialJSON
} from './types';
import { AuthenticationError, ValidationError } from './errors';
import { ValidationUtils, TokenManager } from './utils';

/**
 * Authentication operations
 */
export class Auth {
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
    // Validate input
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
   * Sign in user with email/username and password
   */
  async signIn(request: SignInRequest): Promise<AuthResponse> {
    // Validate input
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
      return response.data as any; // Return MFA challenge response
    }

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
      // Call onSignOut callback if it exists
      if (this.onSignOut) {
        this.onSignOut();
      }
    }
  }

  /**
   * Refresh access token
   */
  async refreshToken(request?: RefreshTokenRequest): Promise<TokenResponse> {
    // If no request provided, get refresh token from tokenManager
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

    // Store new tokens
    if (response.data.access_token && response.data.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: Date.now() + ((response.data as any).expires_in * 1000)
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

  /**
   * Request password reset email
   */
  async forgotPassword(request: ForgotPasswordRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/forgot', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Request password reset email
   */
  async requestPasswordReset(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/reset-request', {
      email
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Reset password with token
   */
  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/confirm', {
      token,
      password: newPassword
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.put<{ message: string }>('/api/v1/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  }

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/email/verify', {
      token
    }, { skipAuth: true });
    return response.data;
  }

  /**
   * Resend email verification
   */
  async resendVerificationEmail(): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/email/resend-verification');
    return response.data;
  }

  /**
   * Send magic link for passwordless authentication
   */
  async sendMagicLink(request: MagicLinkRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/magic-link', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Resend magic link
   */
  async resendMagicLink(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/magic-link/resend', {
      email
    }, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Verify magic link token and sign in
   */
  async verifyMagicLink(token: string): Promise<AuthResponse> {
    try {
      const response = await this.http.post<AuthResponse>('/api/v1/auth/magic-link/verify', {
        token
      }, { skipAuth: true });

      // Store tokens
      if (response.data.tokens && response.data.tokens.access_token && response.data.tokens.refresh_token) {
        await this.tokenManager.setTokens({
          access_token: response.data.tokens.access_token,
          refresh_token: response.data.tokens.refresh_token,
          expires_at: Date.now() + (response.data.tokens.expires_in * 1000)
        });
      }

      // Call onSignIn callback if it exists
      if (this.onSignIn) {
        this.onSignIn({ user: response.data.user });
      }

      return response.data;
    } catch (error) {
      // Re-throw the error to let tests catch it
      throw error;
    }
  }

  // MFA Operations

  /**
   * Get MFA status for current user
   */
  async getMFAStatus(): Promise<MFAStatusResponse> {
    const response = await this.http.get<MFAStatusResponse>('/api/v1/mfa/status');
    return response.data;
  }

  /**
   * Enable MFA (returns QR code and backup codes)
   */
  async enableMFA(method: string): Promise<MFAEnableResponse> {
    const response = await this.http.post<MFAEnableResponse>('/api/v1/auth/mfa/enable', { method });
    return response.data;
  }

  /**
   * Verify MFA setup with TOTP code
   */
  async verifyMFA(request: MFAVerifyRequest): Promise<AuthResponse> {
    if (!/^\d{6}$/.test(request.code)) {
      throw new ValidationError('MFA code must be 6 digits');
    }

    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/mfa/verify', request);

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
   * Disable MFA
   */
  async disableMFA(password: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/mfa/disable', { password });
    return response.data;
  }

  /**
   * Regenerate MFA backup codes
   */
  async regenerateMFABackupCodes(password: string): Promise<MFABackupCodesResponse> {
    const response = await this.http.post<MFABackupCodesResponse>('/api/v1/mfa/regenerate-backup-codes', {
      password
    });
    return response.data;
  }

  /**
   * Validate MFA code (for testing)
   */
  async validateMFACode(code: string): Promise<{ valid: boolean; message: string }> {
    if (!/^\d{6}$/.test(code) && !/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) {
      throw new ValidationError('Invalid MFA code format');
    }

    const response = await this.http.post<{ valid: boolean; message: string }>('/api/v1/mfa/validate-code', {
      code
    });
    return response.data;
  }

  /**
   * Get MFA recovery options
   */
  async getMFARecoveryOptions(email: string): Promise<{
    recovery_available: boolean;
    methods: {
      backup_codes: boolean;
      email_recovery: boolean;
    };
  }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.get(`/api/v1/mfa/recovery-options?email=${encodeURIComponent(email)}`, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Initiate MFA recovery
   */
  async initiateMFARecovery(email: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/mfa/initiate-recovery', {
      email
    }, { skipAuth: true });
    return response.data;
  }

  // OAuth Operations

  /**
   * Get available OAuth providers
   */
  async getOAuthProviders(): Promise<Array<{ provider?: string; name: string; enabled: boolean }>> {
    const response = await this.http.get<OAuthProvidersResponse>('/api/v1/auth/oauth/providers', {
      skipAuth: true
    });
    return response.data.providers;
  }

  /**
   * Initiate OAuth authorization flow
   */
  /**
   * Sign in with OAuth provider
   */
  async signInWithOAuth(params: { provider: string; redirect_uri: string }): Promise<{
    authorization_url: string;
  }> {
    const response = await this.http.get('/api/v1/auth/oauth/authorize', {
      params
    });
    return response.data;
  }

  async initiateOAuth(
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
    const params: Record<string, any> = {};

    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }
    if (options?.redirect_to) {
      params.redirect_to = options.redirect_to;
    }
    if (options?.scopes) {
      params.scopes = options.scopes.join(',');
    }

    const response = await this.http.post<{ authorization_url: string; state: string; provider: string }>(`/api/v1/auth/oauth/authorize/${provider}`, null, {
      params,
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Handle OAuth callback
   */
  async handleOAuthCallback(code: string, state: string): Promise<AuthResponse> {
    const response = await this.http.post<AuthApiResponse>('/api/v1/auth/oauth/callback', {
      code,
      state
    }, {
      skipAuth: true
    });

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
   * Handle OAuth callback (with provider - for advanced use)
   */
  async handleOAuthCallbackWithProvider(
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
  async linkOAuthAccount(
    provider: OAuthProvider,
    options?: {
      redirect_uri?: string;
    }
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

    const response = await this.http.post<{ authorization_url: string; state: string; provider: string; action: string }>(`/api/v1/auth/oauth/link/${provider}`, null, {
      params
    });
    return response.data;
  }

  /**
   * Unlink OAuth account from current user
   */
  async unlinkOAuthAccount(provider: OAuthProvider): Promise<{
    message: string;
    provider: string;
  }> {
    const response = await this.http.delete<{ message: string; provider: string }>(`/api/v1/auth/oauth/unlink/${provider}`);
    return response.data;
  }

  /**
   * Get linked OAuth accounts for current user
   */
  async getLinkedAccounts(): Promise<LinkedAccountsResponse> {
    const response = await this.http.get<LinkedAccountsResponse>('/api/v1/auth/oauth/accounts');
    return response.data;
  }

  // Passkey Operations

  /**
   * Check WebAuthn availability
   */
  async checkPasskeyAvailability(): Promise<{
    available: boolean;
    platform_authenticator: boolean;
    roaming_authenticator: boolean;
    conditional_mediation: boolean;
    user_verifying_platform_authenticator: boolean;
  }> {
    const response = await this.http.get('/api/v1/passkeys/availability', {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Get passkey registration options
   */
  async getPasskeyRegistrationOptions(options?: {
    name?: string;
    authenticator_attachment?: 'platform' | 'cross-platform';
  }): Promise<{
    challenge: string;
    rp: { id: string; name: string };
    user: { id: string; name: string; displayName: string };
    pubKeyCredParams: Array<{ type: string; alg: number }>;
    timeout: number;
    excludeCredentials: Array<{ id: string; type: string }>;
    authenticatorSelection: {
      authenticatorAttachment?: 'platform' | 'cross-platform';
      residentKey?: 'discouraged' | 'preferred' | 'required';
      requireResidentKey?: boolean;
      userVerification?: 'required' | 'preferred' | 'discouraged';
    };
    attestation: string;
  }> {
    type PasskeyRegisterOptions = {
      challenge: string;
      rp: { id: string; name: string };
      user: { id: string; name: string; displayName: string };
      pubKeyCredParams: Array<{ type: string; alg: number }>;
      timeout: number;
      excludeCredentials: Array<{ id: string; type: string }>;
      authenticatorSelection: {
        authenticatorAttachment?: 'platform' | 'cross-platform';
        residentKey?: 'discouraged' | 'preferred' | 'required';
        requireResidentKey?: boolean;
        userVerification?: 'required' | 'preferred' | 'discouraged';
      };
      attestation: string;
    };
    const response = await this.http.post<PasskeyRegisterOptions>('/api/v1/passkeys/register/options', options || {});
    return response.data;
  }

  /**
   * Verify passkey registration
   */
  async verifyPasskeyRegistration(
    credential: PublicKeyCredentialJSON,
    name?: string
  ): Promise<{
    verified: boolean;
    passkey_id: string;
    message: string;
  }> {
    const response = await this.http.post<{ verified: boolean; passkey_id: string; message: string }>('/api/v1/passkeys/register/verify', {
      credential,
      name
    });
    return response.data;
  }

  /**
   * Get passkey authentication options
   */
  async getPasskeyAuthenticationOptions(email?: string): Promise<{
    challenge: string;
    rpId: string;
    timeout: number;
    allowCredentials: Array<{ id: string; type: string }>;
    userVerification: string;
  }> {
    type PasskeyAuthOptions = {
      challenge: string;
      rpId: string;
      timeout: number;
      allowCredentials: Array<{ id: string; type: string }>;
      userVerification: string;
    };
    const data = email ? { email } : {};
    const response = await this.http.post<PasskeyAuthOptions>('/api/v1/passkeys/authenticate/options', data, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Verify passkey authentication
   */
  async verifyPasskeyAuthentication(
    credential: PublicKeyCredentialJSON,
    challenge: string,
    email?: string
  ): Promise<{
    verified: boolean;
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    user: User;
  }> {
    type PasskeyAuthResponse = {
      verified: boolean;
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: User;
      tokens?: { access_token: string; refresh_token: string; expires_in: number };
    };
    const response = await this.http.post<PasskeyAuthResponse>('/api/v1/passkeys/authenticate/verify', {
      credential,
      challenge,
      email
    }, { skipAuth: true });

    // Store tokens
    if (response.data.tokens && response.data.tokens.access_token && response.data.tokens.refresh_token) {
      await this.tokenManager.setTokens({
        access_token: response.data.tokens.access_token,
        refresh_token: response.data.tokens.refresh_token,
        expires_at: Date.now() + (response.data.tokens.expires_in * 1000)
      });
    }

    // Call onSignIn callback if it exists
    if (this.onSignIn) {
      this.onSignIn({ user: response.data.user });
    }

    return response.data;
  }

  /**
   * List user's passkeys
   */
  async listPasskeys(): Promise<Passkey[]> {
    const response = await this.http.get<Passkey[]>('/api/v1/passkeys/');
    return response.data;
  }

  /**
   * Update passkey name
   */
  async updatePasskey(passkeyId: string, name: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.patch<Passkey>(`/api/v1/passkeys/${passkeyId}`, {
      name
    });
    return response.data;
  }

  /**
   * Delete passkey
   */
  async deletePasskey(passkeyId: string, password: string): Promise<{ message: string }> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.delete<{ message: string }>(`/api/v1/passkeys/${passkeyId}`, {
      data: { password }
    });
    return response.data;
  }

  /**
   * Regenerate passkey secret
   */
  async regeneratePasskeySecret(passkeyId: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.post<Passkey>(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
    return response.data;
  }
}
