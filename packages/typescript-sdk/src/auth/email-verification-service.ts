/**
 * Email Verification Service
 * Handles email verification operations
 */

import type { HttpClient } from '../http-client';

export class EmailVerificationService {
  constructor(private http: HttpClient) {}

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/verify-email',
      { token },
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Resend verification email
   */
  async resendVerificationEmail(): Promise<{ message: string }> {
    const response = await this.http.post<{ message: string }>('/api/v1/auth/verify-email/resend', {});
    return response.data;
  }
}
