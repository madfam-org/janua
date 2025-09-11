/**
 * Authentication module for the Plinto TypeScript SDK
 */

import type { HttpClient } from './http-client';
import type {
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  MagicLinkRequest,
  AuthResponse,
  TokenResponse,
  User,
  MFAEnableRequest,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFADisableRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  OAuthProvider,
  OAuthProvidersResponse,
  LinkedAccountsResponse,
  Passkey
} from './types';
import { AuthenticationError, ValidationError } from './errors';
import { ValidationUtils } from './utils';

/**
 * Authentication operations
 */
export class Auth {
  constructor(private http: HttpClient) {}

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
      throw new ValidationError('Password validation failed', {
        violations: { password: passwordValidation.errors }
      });
    }

    if (request.username && !ValidationUtils.isValidUsername(request.username)) {
      throw new ValidationError('Invalid username format');
    }

    const response = await this.http.post<AuthResponse>('/api/v1/auth/signup', request);
    return response.data;
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

    const response = await this.http.post<AuthResponse>('/api/v1/auth/signin', request);
    return response.data;
  }

  /**
   * Sign out current user
   */
  async signOut(): Promise<void> {
    await this.http.post('/api/v1/auth/signout');
  }

  /**
   * Refresh access token
   */
  async refreshToken(request: RefreshTokenRequest): Promise<TokenResponse> {
    const response = await this.http.post<TokenResponse>('/api/v1/auth/refresh', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Get current user information
   */
  async getCurrentUser(): Promise<User> {
    const response = await this.http.get<User>('/api/v1/auth/me');
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
   * Reset password with token
   */
  async resetPassword(request: ResetPasswordRequest): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(request.new_password);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed', {
        violations: { password: passwordValidation.errors }
      });
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/reset', request, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(request: ChangePasswordRequest): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(request.new_password);
    if (!passwordValidation.isValid) {
      throw new ValidationError('Password validation failed', {
        violations: { password: passwordValidation.errors }
      });
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/change', request);
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
   * Verify magic link token and sign in
   */
  async verifyMagicLink(token: string): Promise<AuthResponse> {
    const response = await this.http.post<AuthResponse>('/api/v1/auth/magic-link/verify', {
      token
    }, { skipAuth: true });
    return response.data;
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
  async enableMFA(request: MFAEnableRequest): Promise<MFAEnableResponse> {
    const response = await this.http.post<MFAEnableResponse>('/api/v1/mfa/enable', request);
    return response.data;
  }

  /**
   * Verify MFA setup with TOTP code
   */
  async verifyMFA(request: MFAVerifyRequest): Promise<{ message: string }> {
    if (!/^\d{6}$/.test(request.code)) {
      throw new ValidationError('MFA code must be 6 digits');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/mfa/verify', request);
    return response.data;
  }

  /**
   * Disable MFA
   */
  async disableMFA(request: MFADisableRequest): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/mfa/disable', request);
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
  async getOAuthProviders(): Promise<OAuthProvidersResponse> {
    const response = await this.http.get<OAuthProvidersResponse>('/api/v1/auth/oauth/providers', {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Initiate OAuth authorization flow
   */
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

    const response = await this.http.post(`/api/v1/auth/oauth/authorize/${provider}`, null, {
      params,
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Handle OAuth callback (typically called by your backend)
   */
  async handleOAuthCallback(
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
    const params: Record<string, any> = {};
    
    if (options?.redirect_uri) {
      params.redirect_uri = options.redirect_uri;
    }

    const response = await this.http.post(`/api/v1/auth/oauth/link/${provider}`, null, {
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
    const response = await this.http.delete(`/api/v1/auth/oauth/unlink/${provider}`);
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
    authenticator_attachment?: 'platform' | 'cross-platform';
  }): Promise<{
    challenge: string;
    rp: { id: string; name: string };
    user: { id: string; name: string; displayName: string };
    pubKeyCredParams: Array<{ type: string; alg: number }>;
    timeout: number;
    excludeCredentials: Array<{ id: string; type: string }>;
    authenticatorSelection: any;
    attestation: string;
  }> {
    const response = await this.http.post('/api/v1/passkeys/register/options', options || {});
    return response.data;
  }

  /**
   * Verify passkey registration
   */
  async verifyPasskeyRegistration(
    credential: any,
    name?: string
  ): Promise<{
    verified: boolean;
    passkey_id: string;
    message: string;
  }> {
    const response = await this.http.post('/api/v1/passkeys/register/verify', {
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
    const data = email ? { email } : {};
    const response = await this.http.post('/api/v1/passkeys/authenticate/options', data, {
      skipAuth: true
    });
    return response.data;
  }

  /**
   * Verify passkey authentication
   */
  async verifyPasskeyAuthentication(
    credential: any,
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
    const response = await this.http.post('/api/v1/passkeys/authenticate/verify', {
      credential,
      challenge,
      email
    }, { skipAuth: true });
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
    if (!ValidationUtils.isValidUUID(passkeyId)) {
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
    if (!ValidationUtils.isValidUUID(passkeyId)) {
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
    if (!ValidationUtils.isValidUUID(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.post<Passkey>(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
    return response.data;
  }
}