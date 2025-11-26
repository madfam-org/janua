/**
 * Password Management Service
 * Handles password reset, change, and recovery operations
 */

import type { HttpClient } from '../http-client';
import type { ForgotPasswordRequest } from '../types';
import { ValidationError } from '../errors';
import { ValidationUtils } from '../utils';

export class PasswordService {
  constructor(private http: HttpClient) {}

  /**
   * Request password reset (legacy method)
   */
  async forgotPassword(request: ForgotPasswordRequest): Promise<{ message: string }> {
    if (!ValidationUtils.isValidEmail(request.email)) {
      throw new ValidationError('Invalid email format');
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/forgot-password', request, {
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

    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/password/reset/request',
      { email },
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Reset password with token
   */
  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError(
        'Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.post<{ message: string }>(
      '/api/v1/auth/password/reset',
      { token, new_password: newPassword },
      { skipAuth: true }
    );
    return response.data;
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const passwordValidation = ValidationUtils.validatePassword(newPassword);
    if (!passwordValidation.isValid) {
      throw new ValidationError(
        'Password validation failed',
        passwordValidation.errors.map(err => ({ field: 'password', message: err }))
      );
    }

    const response = await this.http.post<{ message: string }>('/api/v1/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  }
}
