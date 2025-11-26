/**
 * Passkey/WebAuthn authentication service for the Janua TypeScript SDK
 */

import type { HttpClient } from '../http-client';
import type { User, Passkey, PublicKeyCredentialJSON } from '../types';
import type { TokenManager } from '../utils';
import { ValidationError } from '../errors';
import { ValidationUtils } from '../utils';

/**
 * Passkey registration options response type
 */
export interface PasskeyRegistrationOptions {
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
}

/**
 * Passkey authentication options response type
 */
export interface PasskeyAuthenticationOptions {
  challenge: string;
  rpId: string;
  timeout: number;
  allowCredentials: Array<{ id: string; type: string }>;
  userVerification: string;
}

/**
 * Passkey authentication operations
 */
export class PasskeyService {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void
  ) {}

  /**
   * Check WebAuthn availability
   */
  async checkAvailability(): Promise<{
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
  async getRegistrationOptions(options?: {
    name?: string;
    authenticator_attachment?: 'platform' | 'cross-platform';
  }): Promise<PasskeyRegistrationOptions> {
    const response = await this.http.post<PasskeyRegistrationOptions>(
      '/api/v1/passkeys/register/options',
      options || {}
    );
    return response.data;
  }

  /**
   * Verify passkey registration
   */
  async verifyRegistration(
    credential: PublicKeyCredentialJSON,
    name?: string
  ): Promise<{
    verified: boolean;
    passkey_id: string;
    message: string;
  }> {
    const response = await this.http.post<{
      verified: boolean;
      passkey_id: string;
      message: string;
    }>('/api/v1/passkeys/register/verify', { credential, name });
    return response.data;
  }

  /**
   * Get passkey authentication options
   */
  async getAuthenticationOptions(email?: string): Promise<PasskeyAuthenticationOptions> {
    const data = email ? { email } : {};
    const response = await this.http.post<PasskeyAuthenticationOptions>(
      '/api/v1/passkeys/authenticate/options',
      data,
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Verify passkey authentication
   */
  async verifyAuthentication(
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
    interface PasskeyAuthResponse {
      verified: boolean;
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: User;
      tokens?: { access_token: string; refresh_token: string; expires_in: number };
    }

    const response = await this.http.post<PasskeyAuthResponse>(
      '/api/v1/passkeys/authenticate/verify',
      { credential, challenge, email },
      { skipAuth: true }
    );

    // Store tokens
    if (response.data.tokens?.access_token && response.data.tokens?.refresh_token) {
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
  async list(): Promise<Passkey[]> {
    const response = await this.http.get<Passkey[]>('/api/v1/passkeys/');
    return response.data;
  }

  /**
   * Update passkey name
   */
  async update(passkeyId: string, name: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.patch<Passkey>(`/api/v1/passkeys/${passkeyId}`, { name });
    return response.data;
  }

  /**
   * Delete passkey
   */
  async delete(passkeyId: string, password: string): Promise<{ message: string }> {
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
  async regenerateSecret(passkeyId: string): Promise<Passkey> {
    if (!ValidationUtils.isValidUuid(passkeyId)) {
      throw new ValidationError('Invalid passkey ID format');
    }

    const response = await this.http.post<Passkey>(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
    return response.data;
  }
}
