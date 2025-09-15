/**
 * Tests for Magic Link operations
 */

import { Auth } from '../../auth';
import { AuthenticationError } from '../../errors';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { userFixtures, tokenFixtures } from '../../../../../tests/fixtures/data';

describe('Auth - Magic Link Operations', () => {
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

  describe('sendMagicLink', () => {
    it('should send magic link successfully', async () => {
      const request = { email: 'user@example.com' };
      const mockResponse = { message: 'Magic link sent successfully' };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.sendMagicLink(request);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/magic-link', request, {
        skipAuth: true
      });
      expect(result).toEqual(mockResponse);
    });

    it('should send magic link with additional options', async () => {
      const request = { 
        email: 'user@example.com',
        redirect_url: 'https://app.example.com/dashboard',
        expires_in: 600
      };
      const mockResponse = { message: 'Magic link sent successfully' };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.sendMagicLink(request);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/magic-link', request, {
        skipAuth: true
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('verifyMagicLink', () => {
    it('should verify magic link successfully', async () => {
      const token = 'magic_link_token_123';
      const mockResponse = {
        user: userFixtures.validUser,
        tokens: tokenFixtures.validTokens,
        message: 'Magic link verified successfully'
      };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.verifyMagicLink(token);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/magic-link/verify', {
        token: token
      }, { skipAuth: true });
      expect(result).toEqual(mockResponse);
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.tokens.access_token,
        refresh_token: mockResponse.tokens.refresh_token,
        expires_at: expect.any(Number)
      });
      expect(mockOnSignIn).toHaveBeenCalled();
    });

    it('should handle expired magic link', async () => {
      const token = 'expired_token_123';
      const mockError = new Error('Token expired');

      mockHttpClient.post.mockRejectedValue(mockError);

      await expect(auth.verifyMagicLink(token)).rejects.toThrow();
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(mockOnSignIn).not.toHaveBeenCalled();
    });

    it('should handle invalid magic link', async () => {
      const token = 'invalid_token_123';
      const mockError = new Error('Invalid token');

      mockHttpClient.post.mockRejectedValue(mockError);

      await expect(auth.verifyMagicLink(token)).rejects.toThrow();
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(mockOnSignIn).not.toHaveBeenCalled();
    });
  });

  describe('resendMagicLink', () => {
    it('should resend magic link successfully', async () => {
      const email = 'user@example.com';
      const mockResponse = { message: 'Magic link resent successfully' };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.resendMagicLink(email);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/magic-link/resend', {
        email: email
      }, { skipAuth: true });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('Additional password operations', () => {
    describe('forgotPassword', () => {
      it('should send forgot password email successfully', async () => {
        const request = { email: 'user@example.com' };
        const mockResponse = { message: 'Password reset email sent' };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.forgotPassword(request);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/password/forgot', request, {
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('resendVerificationEmail', () => {
      it('should resend verification email successfully', async () => {
        const mockResponse = { message: 'Verification email sent' };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.resendVerificationEmail();

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/email/resend-verification');
        expect(result).toEqual(mockResponse);
      });
    });
  });

  describe('User Profile operations', () => {
    describe('getCurrentUser', () => {
      it('should get current user successfully', async () => {
        mockHttpClient.get.mockResolvedValue({
          data: userFixtures.verifiedUser
        });

        const result = await auth.getCurrentUser();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/me');
        expect(result).toEqual(userFixtures.verifiedUser);
      });

      it('should return null if not authenticated', async () => {
        mockHttpClient.get.mockRejectedValue(new AuthenticationError('Not authenticated'));

        const result = await auth.getCurrentUser();

        expect(result).toBeNull();
      });
    });

    describe('updateProfile', () => {
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
});