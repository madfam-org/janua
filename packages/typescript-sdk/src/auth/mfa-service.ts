/**
 * Multi-Factor Authentication Service
 * Handles MFA setup, verification, and recovery
 */

import type { HttpClient } from '../http-client';
import type {
  AuthResponse,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  User
} from '../types';
import { TokenManager } from '../utils';

export class MFAService {
  constructor(
    private http: HttpClient,
    private tokenManager: TokenManager,
    private onSignIn?: (data?: { user: User }) => void
  ) {}

  /**
   * Get MFA status for current user
   */
  async getMFAStatus(): Promise<MFAStatusResponse> {
    const response = await this.http.get<MFAStatusResponse>('/api/v1/auth/mfa/status');
    return response.data;
  }

  /**
   * Enable MFA for current user
   */
  async enableMFA(method: string): Promise<MFAEnableResponse> {
    const response = await this.http.post<MFAEnableResponse>('/api/v1/auth/mfa/enable', { method });
    return response.data;
  }

  /**
   * Verify MFA code and complete authentication
   */
  async verifyMFA(request: MFAVerifyRequest): Promise<AuthResponse> {
    const response = await this.http.post<{
      user: User;
      access_token: string;
      refresh_token: string;
      expires_in: number;
      token_type: 'bearer';
    }>('/api/v1/auth/mfa/verify', request, { skipAuth: true });

    // Store tokens
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
   * Disable MFA for current user
   */
  async disableMFA(password: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/mfa/disable', { password });
    return response.data;
  }

  /**
   * Regenerate MFA backup codes
   */
  async regenerateMFABackupCodes(password: string): Promise<MFABackupCodesResponse> {
    const response = await this.http.post<MFABackupCodesResponse>(
      '/api/v1/auth/mfa/backup-codes/regenerate',
      { password }
    );
    return response.data;
  }

  /**
   * Validate MFA code without completing authentication
   */
  async validateMFACode(code: string): Promise<{ valid: boolean; message: string }> {
    const response = await this.http.post<{ valid: boolean; message: string }>(
      '/api/v1/auth/mfa/validate',
      { code }
    );
    return response.data;
  }

  /**
   * Get MFA recovery options for a user
   */
  async getMFARecoveryOptions(email: string): Promise<{
    recovery_methods: Array<{
      type: string;
      hint: string;
    }>;
  }> {
    const response = await this.http.post<{
      recovery_methods: Array<{
        type: string;
        hint: string;
      }>;
    }>('/api/v1/auth/mfa/recovery/options', { email }, { skipAuth: true });
    return response.data;
  }

  /**
   * Initiate MFA recovery process
   */
  async initiateMFARecovery(email: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/mfa/recovery/initiate',
      { email },
      { skipAuth: true }
    );
    return response.data;
  }
}
