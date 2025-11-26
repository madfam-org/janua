/**
 * Tests for basic Auth operations (signUp, signIn, signOut, password management)
 */

import { Auth } from '../../auth';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { AuthenticationError, ValidationError } from '../../errors';
import { UserStatus } from '../../types';
import type { SignUpParams, SignInParams } from '../../types';

// Inline fixtures
const userFixtures = {
  validUser: {
    id: '550e8400-e29b-41d4-a716-446655440000',
    email: 'test@example.com',
    email_verified: true,
    first_name: 'Test',
    last_name: 'User',
    status: UserStatus.ACTIVE,
    mfa_enabled: false,
    is_admin: false,
    phone_verified: false,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    user_metadata: {}
  },
  verifiedUser: {
    id: '550e8400-e29b-41d4-a716-446655440001',
    email: 'verified@example.com',
    email_verified: true,
    first_name: 'Verified',
    last_name: 'User',
    status: UserStatus.ACTIVE,
    mfa_enabled: false,
    is_admin: false,
    phone_verified: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    user_metadata: {}
  }
};

const tokenFixtures = {
  validTokens: {
    access_token: 'valid_access_token',
    refresh_token: 'valid_refresh_token',
    token_type: 'bearer' as const,
    expires_in: 3600
  },
  validAccessToken: 'valid_access_token',
  validRefreshToken: 'valid_refresh_token'
};

describe('Auth - Basic Operations', () => {
  let auth: Auth;
  let mockHttpClient: jest.Mocked<HttpClient>;
  let mockTokenManager: jest.Mocked<TokenManager>;
  let mockOnSignIn: jest.Mock;
  let mockOnSignOut: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();

    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn()
    } as any;

    mockTokenManager = {
      setTokens: jest.fn(),
      clearTokens: jest.fn(),
      getAccessToken: jest.fn(),
      getRefreshToken: jest.fn(),
      hasValidTokens: jest.fn()
    } as any;

    mockOnSignIn = jest.fn();
    mockOnSignOut = jest.fn();

    auth = new Auth(mockHttpClient, mockTokenManager, mockOnSignIn, mockOnSignOut);
  });

  describe('signUp', () => {
    it('should sign up a new user successfully', async () => {
      const signUpParams: SignUpParams = {
        email: 'test@example.com',
        password: 'Test123!@#',
        first_name: 'Test',
        last_name: 'User'
      };

      const mockResponse = {
        user: userFixtures.verifiedUser,
        access_token: tokenFixtures.validAccessToken,
        refresh_token: tokenFixtures.validRefreshToken,
        expires_in: 3600,
        token_type: 'bearer' as const
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signUp(signUpParams);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/register', signUpParams);
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_at: expect.any(Number)
      });
      expect(mockOnSignIn).toHaveBeenCalledWith({ user: mockResponse.user });
      expect(result).toEqual({
        user: mockResponse.user,
        tokens: {
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token,
          expires_in: mockResponse.expires_in,
          token_type: mockResponse.token_type
        }
      });
    });

    it('should handle validation errors during sign up', async () => {
      const signUpParams: SignUpParams = {
        email: 'invalid-email',
        password: 'weak'
      };

      mockHttpClient.post.mockRejectedValue(
        new ValidationError('Validation failed', [
          { field: 'email', message: 'Invalid email format' },
          { field: 'password', message: 'Password too weak' }
        ])
      );

      await expect(auth.signUp(signUpParams)).rejects.toThrow(ValidationError);
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(mockOnSignIn).not.toHaveBeenCalled();
    });
  });

  describe('signIn', () => {
    it('should sign in with email and password', async () => {
      const signInParams: SignInParams = {
        email: 'test@example.com',
        password: 'Test123!@#'
      };

      const mockResponse = {
        user: userFixtures.verifiedUser,
        access_token: tokenFixtures.validAccessToken,
        refresh_token: tokenFixtures.validRefreshToken,
        expires_in: 3600,
        token_type: 'bearer' as const
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signIn(signInParams);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/login', signInParams);
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_at: expect.any(Number)
      });
      expect(mockOnSignIn).toHaveBeenCalledWith({ user: mockResponse.user });
      expect(result).toEqual({
        user: mockResponse.user,
        tokens: {
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token,
          expires_in: mockResponse.expires_in,
          token_type: mockResponse.token_type
        }
      });
    });

    it('should handle authentication errors during sign in', async () => {
      const signInParams: SignInParams = {
        email: 'test@example.com',
        password: 'wrongpassword'
      };

      mockHttpClient.post.mockRejectedValue(
        new AuthenticationError('Invalid credentials')
      );

      await expect(auth.signIn(signInParams)).rejects.toThrow(AuthenticationError);
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(mockOnSignIn).not.toHaveBeenCalled();
    });
  });

  describe('signOut', () => {
    it('should sign out successfully', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue(tokenFixtures.validRefreshToken);
      mockHttpClient.post.mockResolvedValue({ data: { success: true } });

      await auth.signOut();

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/logout', {
        refresh_token: tokenFixtures.validRefreshToken
      });
      expect(mockTokenManager.clearTokens).toHaveBeenCalled();
      expect(mockOnSignOut).toHaveBeenCalled();
    });

    it('should clear tokens even if API call fails', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue(tokenFixtures.validRefreshToken);
      mockHttpClient.post.mockRejectedValue(new Error('Network error'));

      await auth.signOut();

      expect(mockTokenManager.clearTokens).toHaveBeenCalled();
      expect(mockOnSignOut).toHaveBeenCalled();
    });
  });

  describe('refreshToken', () => {
    it('should refresh tokens successfully', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue(tokenFixtures.validRefreshToken);

      const mockResponse = {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        expires_in: 3600,
        token_type: 'bearer' as const
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.refreshToken();

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/refresh', {
        refresh_token: tokenFixtures.validRefreshToken
      }, {
        skipAuth: true
      });
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_at: expect.any(Number)
      });
      expect(result).toEqual({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_in: mockResponse.expires_in,
        token_type: mockResponse.token_type
      });
    });

    it('should throw error if no refresh token available', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue(null);

      await expect(auth.refreshToken()).rejects.toThrow(AuthenticationError);
      expect(mockHttpClient.post).not.toHaveBeenCalled();
    });
  });

  describe('Password Management', () => {
    describe('changePassword', () => {
      it('should change password successfully', async () => {
        const currentPassword = 'CurrentPassword123!';
        const newPassword = 'NewPassword123!@#';

        mockHttpClient.put.mockResolvedValue({
          data: {
            success: true,
            message: 'Password changed successfully'
          }
        });

        const result = await auth.changePassword(currentPassword, newPassword);

        expect(mockHttpClient.put).toHaveBeenCalledWith('/api/v1/auth/password/change', {
          current_password: currentPassword,
          new_password: newPassword
        });
        expect(result).toEqual({
          success: true,
          message: 'Password changed successfully'
        });
      });
    });

    describe('requestPasswordReset', () => {
      it('should request password reset successfully', async () => {
        const email = 'test@example.com';

        mockHttpClient.post.mockResolvedValue({
          data: {
            success: true,
            message: 'Password reset email sent'
          }
        });

        const result = await auth.requestPasswordReset(email);

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/auth/password/reset-request',
          { email },
          { skipAuth: true }
        );
        expect(result).toEqual({
          success: true,
          message: 'Password reset email sent'
        });
      });
    });

    describe('resetPassword', () => {
      it('should reset password successfully', async () => {
        const token = 'reset-token-123';
        const newPassword = 'NewPassword123!@#';

        mockHttpClient.post.mockResolvedValue({
          data: {
            success: true,
            message: 'Password reset successfully'
          }
        });

        const result = await auth.resetPassword(token, newPassword);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/password/confirm', {
          token,
          password: newPassword
        }, {
          skipAuth: true
        });
        expect(result).toEqual({
          success: true,
          message: 'Password reset successfully'
        });
      });
    });
  });

  describe('Email Verification', () => {
    it('should verify email successfully', async () => {
      const token = 'verification-token-123';

      mockHttpClient.post.mockResolvedValue({
        data: {
          success: true,
          message: 'Email verified successfully'
        }
      });

      const result = await auth.verifyEmail(token);

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/email/verify',
        { token },
        { skipAuth: true }
      );
      expect(result).toEqual({
        success: true,
        message: 'Email verified successfully'
      });
    });
  });

  describe('User Profile', () => {
    it('should get current user successfully', async () => {
      mockHttpClient.get.mockResolvedValue({
        data: userFixtures.verifiedUser
      });

      const result = await auth.getCurrentUser();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/me');
      expect(result).toEqual(userFixtures.verifiedUser);
    });

    it('should return null if not authenticated', async () => {
      mockHttpClient.get.mockRejectedValue(
        new AuthenticationError('Not authenticated')
      );

      const result = await auth.getCurrentUser();

      expect(result).toBeNull();
    });

    it('should update user profile successfully', async () => {
      const updates = {
        first_name: 'Updated',
        last_name: 'Name',
        phone: '+1234567890'
      };

      const updatedUser = {
        ...userFixtures.verifiedUser,
        ...updates
      };

      mockHttpClient.patch.mockResolvedValue({
        data: updatedUser
      });

      const result = await auth.updateProfile(updates);

      expect(mockHttpClient.patch).toHaveBeenCalledWith('/api/v1/auth/profile', updates);
      expect(result).toEqual(updatedUser);
    });
  });
});
