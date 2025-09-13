/**
 * Tests for Auth module
 */

import { Auth } from '../auth';
import { HttpClient } from '../http-client';
import { TokenManager } from '../utils';
import { AuthenticationError, ValidationError } from '../errors';
import { authMocks } from '../../../../tests/mocks/api';
import { userFixtures, tokenFixtures } from '../../../../tests/fixtures/data';
import type { SignUpParams, SignInParams, MFAParams, OAuthParams } from '../types';

describe('Auth', () => {
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
        expires_in: 3600
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signUp(signUpParams);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/register', signUpParams);
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_in: mockResponse.expires_in
      });
      expect(mockOnSignIn).toHaveBeenCalledWith({ user: mockResponse.user });
      expect(result).toEqual({
        user: mockResponse.user,
        tokens: {
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token
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
        expires_in: 3600
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signIn(signInParams);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/login', signInParams);
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_in: mockResponse.expires_in
      });
      expect(mockOnSignIn).toHaveBeenCalledWith({ user: mockResponse.user });
      expect(result).toEqual({
        user: mockResponse.user,
        tokens: {
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token
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

    it('should handle MFA requirement', async () => {
      const signInParams: SignInParams = {
        email: 'test@example.com',
        password: 'Test123!@#'
      };

      const mockResponse = {
        requires_mfa: true,
        mfa_challenge_id: 'challenge-123',
        mfa_methods: ['totp', 'sms']
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signIn(signInParams);

      expect(result).toEqual({
        requires_mfa: true,
        mfa_challenge_id: 'challenge-123',
        mfa_methods: ['totp', 'sms']
      });
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
        expires_in: 3600
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.refreshToken();

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/refresh', {
        refresh_token: tokenFixtures.validRefreshToken
      });
      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token,
        expires_in: mockResponse.expires_in
      });
      expect(result).toEqual({
        access_token: mockResponse.access_token,
        refresh_token: mockResponse.refresh_token
      });
    });

    it('should throw error if no refresh token available', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue(null);

      await expect(auth.refreshToken()).rejects.toThrow(AuthenticationError);
      expect(mockHttpClient.post).not.toHaveBeenCalled();
    });
  });

  describe('verifyEmail', () => {
    it('should verify email successfully', async () => {
      const token = 'verification-token-123';
      
      mockHttpClient.post.mockResolvedValue({ 
        data: { 
          success: true,
          message: 'Email verified successfully' 
        } 
      });

      const result = await auth.verifyEmail(token);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/verify-email', { token });
      expect(result).toEqual({ 
        success: true,
        message: 'Email verified successfully' 
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

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/password/reset', { email });
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
      });
      expect(result).toEqual({ 
        success: true,
        message: 'Password reset successfully' 
      });
    });
  });

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

  describe('MFA operations', () => {
    describe('verifyMFA', () => {
      it('should verify MFA code successfully', async () => {
        const mfaParams: MFAParams = {
          challenge_id: 'challenge-123',
          code: '123456',
          method: 'totp'
        };

        const mockResponse = {
          user: userFixtures.verifiedUser,
          access_token: tokenFixtures.validAccessToken,
          refresh_token: tokenFixtures.validRefreshToken,
          expires_in: 3600
        };

        mockHttpClient.post.mockResolvedValue({ data: mockResponse });

        const result = await auth.verifyMFA(mfaParams);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/mfa/verify', mfaParams);
        expect(mockTokenManager.setTokens).toHaveBeenCalled();
        expect(mockOnSignIn).toHaveBeenCalled();
        expect(result).toEqual({
          user: mockResponse.user,
          tokens: {
            access_token: mockResponse.access_token,
            refresh_token: mockResponse.refresh_token
          }
        });
      });
    });

    describe('enableMFA', () => {
      it('should enable MFA successfully', async () => {
        const method = 'totp';
        
        mockHttpClient.post.mockResolvedValue({ 
          data: { 
            secret: 'MFASECRET123',
            qr_code: 'data:image/png;base64,...',
            backup_codes: ['code1', 'code2', 'code3']
          } 
        });

        const result = await auth.enableMFA(method);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/mfa/enable', { method });
        expect(result).toEqual({ 
          secret: 'MFASECRET123',
          qr_code: 'data:image/png;base64,...',
          backup_codes: ['code1', 'code2', 'code3']
        });
      });
    });

    describe('disableMFA', () => {
      it('should disable MFA successfully', async () => {
        const password = 'CurrentPassword123!';
        
        mockHttpClient.post.mockResolvedValue({ 
          data: { 
            success: true,
            message: 'MFA disabled successfully' 
          } 
        });

        const result = await auth.disableMFA(password);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/mfa/disable', { password });
        expect(result).toEqual({ 
          success: true,
          message: 'MFA disabled successfully' 
        });
      });
    });
  });

  describe('OAuth operations', () => {
    describe('signInWithOAuth', () => {
      it('should initiate OAuth sign in', async () => {
        const oauthParams: OAuthParams = {
          provider: 'google',
          redirect_uri: 'http://localhost:3000/auth/callback'
        };

        mockHttpClient.get.mockResolvedValue({ 
          data: { 
            authorization_url: 'https://accounts.google.com/oauth/authorize?...'
          } 
        });

        const result = await auth.signInWithOAuth(oauthParams);

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/authorize', {
          params: oauthParams
        });
        expect(result).toEqual({ 
          authorization_url: 'https://accounts.google.com/oauth/authorize?...'
        });
      });
    });

    describe('handleOAuthCallback', () => {
      it('should handle OAuth callback successfully', async () => {
        const code = 'oauth-code-123';
        const state = 'state-123';

        const mockResponse = {
          user: userFixtures.verifiedUser,
          access_token: tokenFixtures.validAccessToken,
          refresh_token: tokenFixtures.validRefreshToken,
          expires_in: 3600
        };

        mockHttpClient.post.mockResolvedValue({ data: mockResponse });

        const result = await auth.handleOAuthCallback(code, state);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/oauth/callback', { 
          code,
          state 
        });
        expect(mockTokenManager.setTokens).toHaveBeenCalled();
        expect(mockOnSignIn).toHaveBeenCalled();
        expect(result).toEqual({
          user: mockResponse.user,
          tokens: {
            access_token: mockResponse.access_token,
            refresh_token: mockResponse.refresh_token
          }
        });
      });
    });

    describe('getOAuthProviders', () => {
      it('should get OAuth providers list', async () => {
        const mockProviders = [
          { name: 'google', enabled: true },
          { name: 'github', enabled: true },
          { name: 'microsoft', enabled: false }
        ];

        mockHttpClient.get.mockResolvedValue({ 
          data: { 
            providers: mockProviders
          } 
        });

        const result = await auth.getOAuthProviders();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/providers');
        expect(result).toEqual(mockProviders);
      });
    });
  });

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
      mockHttpClient.get.mockRejectedValue(
        new AuthenticationError('Not authenticated')
      );

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

      mockHttpClient.put.mockResolvedValue({ 
        data: updatedUser
      });

      const result = await auth.updateProfile(updates);

      expect(mockHttpClient.put).toHaveBeenCalledWith('/api/v1/auth/me', updates);
      expect(result).toEqual(updatedUser);
    });
  });
});