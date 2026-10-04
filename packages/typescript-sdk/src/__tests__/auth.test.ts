/**
 * Tests for Auth module
 */

import { Auth } from '../auth';
import { HttpClient } from '../http-client';
import { TokenManager } from '../utils';
import { AuthenticationError, ValidationError } from '../errors';
import { OAuthProvider, UserStatus } from '../types';
import type { SignUpParams, SignInParams, OAuthParams } from '../types';

// Inline fixtures to replace missing imports
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

describe('Auth', () => {
  let auth: Auth;
  let mockHttpClient: jest.Mocked<HttpClient>;
  let mockTokenManager: jest.Mocked<TokenManager>;
  let mockOnSignIn: jest.Mock;
  let mockOnSignOut: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();

    mockHttpClient = {
      emit: jest.fn(),
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

    it('should surface an MFA challenge (mfa_required + mfa_token)', async () => {
      const signInParams: SignInParams = {
        email: 'test@example.com',
        password: 'Test123!@#'
      };

      // Real API contract (apps/api/app/routers/v1/auth.py:451-452): on a second
      // factor, sign-in returns the user, mfa_required=true, an mfa_token, and NO
      // tokens.
      const mockResponse = {
        user: userFixtures.validUser,
        tokens: null,
        mfa_required: true,
        mfa_token: 'mfa-token-abc'
      };

      mockHttpClient.post.mockResolvedValue({ data: mockResponse });

      const result = await auth.signIn(signInParams);

      expect(result).toEqual({
        user: userFixtures.validUser,
        mfa_required: true,
        mfa_token: 'mfa-token-abc'
      });
      // No tokens are issued until verifyMfaChallenge completes the second factor.
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

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/email/verify', { token }, { skipAuth: true });
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

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/password/reset-request', { email }, { skipAuth: true });
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
    describe('verifyMFA (enrollment)', () => {
      it('should confirm enrollment and return a message', async () => {
        const mockResponse = { message: 'MFA successfully enabled' };

        mockHttpClient.post.mockResolvedValue({ data: mockResponse });

        const result = await auth.verifyMFA({ code: '123456' });

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/verify', { code: '123456' });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('verifyMfaChallenge (sign-in)', () => {
      it('should complete the challenge and issue tokens', async () => {
        const mockResponse = {
          user: userFixtures.verifiedUser,
          tokens: {
            access_token: tokenFixtures.validAccessToken,
            refresh_token: tokenFixtures.validRefreshToken,
            expires_in: 3600,
            token_type: 'bearer' as const
          }
        };

        mockHttpClient.post.mockResolvedValue({ data: mockResponse });

        const result = await auth.verifyMfaChallenge('mfa-token-abc', '123456');

        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/mfa/challenge/verify',
          { mfa_token: 'mfa-token-abc', code: '123456' },
          { skipAuth: true }
        );
        expect(mockTokenManager.setTokens).toHaveBeenCalled();
        expect(mockOnSignIn).toHaveBeenCalled();
        expect(result).toEqual({
          user: mockResponse.user,
          tokens: mockResponse.tokens
        });
      });
    });

    describe('enableMFA', () => {
      it('should begin enrollment with the account password', async () => {
        const password = 'CurrentPassword123!';

        mockHttpClient.post.mockResolvedValue({
          data: {
            secret: 'MFASECRET123',
            qr_code: 'data:image/png;base64,...',
            backup_codes: ['code1', 'code2', 'code3'],
            provisioning_uri: 'otpauth://totp/Janua:test'
          }
        });

        const result = await auth.enableMFA(password);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/enable', { password });
        expect(result).toEqual({
          secret: 'MFASECRET123',
          qr_code: 'data:image/png;base64,...',
          backup_codes: ['code1', 'code2', 'code3'],
          provisioning_uri: 'otpauth://totp/Janua:test'
        });
      });
    });

    describe('disableMFA', () => {
      it('should disable MFA successfully', async () => {
        const password = 'CurrentPassword123!';

        mockHttpClient.post.mockResolvedValue({
          data: {
            message: 'MFA successfully disabled'
          }
        });

        const result = await auth.disableMFA(password);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/disable', { password });
        expect(result).toEqual({
          message: 'MFA successfully disabled'
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
          expires_in: 3600,
          token_type: 'bearer' as const
        };

        mockHttpClient.post.mockResolvedValue({ data: mockResponse });

        const result = await auth.handleOAuthCallback(code, state);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/oauth/callback', {
          code,
          state
        }, {
          skipAuth: true
        });
        expect(mockTokenManager.setTokens).toHaveBeenCalled();
        expect(mockOnSignIn).toHaveBeenCalled();
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

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/providers', {
          skipAuth: true
        });
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

      mockHttpClient.patch.mockResolvedValue({
        data: updatedUser
      });

      const result = await auth.updateProfile(updates);

      expect(mockHttpClient.patch).toHaveBeenCalledWith('/api/v1/auth/profile', updates);
      expect(result).toEqual(updatedUser);
    });
  });

  describe('Magic Link operations', () => {
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
    });
  });

  describe('Extended MFA operations', () => {
    describe('getMFAStatus', () => {
      it('should get MFA status successfully', async () => {
        const mockResponse = {
          enabled: true,
          methods: ['totp', 'sms'],
          backup_codes_count: 8
        };

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.getMFAStatus();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/mfa/status');
        expect(result).toEqual(mockResponse);
      });
    });

    describe('regenerateMFABackupCodes', () => {
      it('should regenerate MFA backup codes successfully', async () => {
        const password = 'userpassword123';
        const mockResponse = {
          backup_codes: ['code1', 'code2', 'code3'],
          message: 'Backup codes regenerated successfully'
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.regenerateMFABackupCodes(password);

        // `password` is a QUERY parameter on the handler, sent via `params`.
        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/mfa/regenerate-backup-codes',
          undefined,
          { params: { password } }
        );
        expect(result).toEqual(mockResponse);
      });
    });

    describe('validateMFACode', () => {
      it('should validate MFA code successfully', async () => {
        const code = '123456';
        const mockResponse = { valid: true, message: 'Code is valid' };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.validateMFACode(code);

        // `code` is a QUERY parameter on the handler, sent via `params`.
        expect(mockHttpClient.post).toHaveBeenCalledWith(
          '/api/v1/mfa/validate-code',
          undefined,
          { params: { code } }
        );
        expect(result).toEqual(mockResponse);
      });
    });

    describe('getMFARecoveryOptions', () => {
      it('should get MFA recovery options successfully', async () => {
        const email = 'user@example.com';
        const mockResponse = {
          options: ['backup_codes', 'sms', 'email'],
          available_methods: ['sms'],
          message: 'Recovery options available'
        };

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.getMFARecoveryOptions(email);

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/mfa/recovery-options?email=user%40example.com', {
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('initiateMFARecovery', () => {
      it('should initiate MFA recovery successfully', async () => {
        const email = 'user@example.com';
        const mockResponse = { message: 'MFA recovery initiated successfully' };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.initiateMFARecovery(email);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/initiate-recovery', {
          email: email
        }, { skipAuth: true });
        expect(result).toEqual(mockResponse);
      });
    });
  });

  describe('Extended OAuth operations', () => {
    describe('initiateOAuth', () => {
      it('should initiate OAuth flow successfully', async () => {
        const provider = OAuthProvider.GOOGLE;
        const options = {
          redirect_uri: 'https://app.example.com/callback',
          scopes: ['email', 'profile']
        };
        const mockResponse = {
          authorization_url: 'https://oauth.google.com/auth?client_id=123&redirect_uri=...',
          state: 'random_state_123',
          provider: 'google'
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.initiateOAuth(provider, options);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/oauth/authorize/google', null, {
          params: {
            redirect_uri: 'https://app.example.com/callback',
            scopes: 'email,profile'
          },
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('handleOAuthCallbackWithProvider', () => {
      it('should handle OAuth callback with provider successfully', async () => {
        const provider = OAuthProvider.GOOGLE;
        const code = 'oauth_code_123';
        const state = 'state_123';
        const mockResponse = {
          user: userFixtures.validUser,
          access_token: tokenFixtures.validTokens.access_token,
          refresh_token: tokenFixtures.validTokens.refresh_token,
          token_type: tokenFixtures.validTokens.token_type,
          expires_in: tokenFixtures.validTokens.expires_in,
          message: 'OAuth authentication successful'
        };

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.handleOAuthCallbackWithProvider(provider, code, state);

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/callback/google', {
          params: { code: code, state: state },
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
        expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token,
          expires_at: expect.any(Number)
        });
        expect(mockOnSignIn).toHaveBeenCalled();
      });
    });

    describe('linkOAuthAccount', () => {
      it('should link OAuth account successfully', async () => {
        const provider = OAuthProvider.GITHUB;
        const options = { redirect_uri: 'https://app.example.com/link-callback' };
        const mockResponse = {
          authorization_url: 'https://github.com/login/oauth/authorize?client_id=123&redirect_uri=...',
          state: 'random_state_456',
          provider: 'github',
          action: 'link'
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.linkOAuthAccount(provider, options);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/auth/oauth/link/github', null, {
          params: {
            redirect_uri: 'https://app.example.com/link-callback'
          }
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('unlinkOAuthAccount', () => {
      it('should unlink OAuth account successfully', async () => {
        const provider = OAuthProvider.GITHUB;
        const mockResponse = {
          message: 'OAuth account unlinked successfully'
        };

        mockHttpClient.delete.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.unlinkOAuthAccount(provider);

        expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/auth/oauth/unlink/${provider}`);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('getLinkedAccounts', () => {
      it('should get linked accounts successfully', async () => {
        const mockResponse = {
          linked_accounts: [
            {
              provider: 'google',
              external_id: 'google123',
              email: 'user@google.com',
              linked_at: '2023-01-01T00:00:00Z'
            },
            {
              provider: 'github',
              external_id: 'github456',
              email: 'user@github.com',
              linked_at: '2023-01-02T00:00:00Z'
            }
          ]
        };

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.getLinkedAccounts();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/accounts');
        expect(result).toEqual(mockResponse);
      });
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

  describe('Passkey operations', () => {
    describe('checkPasskeyAvailability', () => {
      it('should check passkey availability successfully', async () => {
        const mockResponse = {
          available: true,
          supported_authenticators: ['platform', 'cross-platform'],
          message: 'Passkeys are supported'
        };

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.checkPasskeyAvailability();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/passkeys/availability', {
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('getPasskeyRegistrationOptions', () => {
      it('should get passkey registration options successfully', async () => {
        const options = { authenticator_attachment: 'platform' as const };
        const mockResponse = {
          challenge: 'registration_challenge_123',
          rp: { name: 'My App', id: 'app.example.com' },
          user: { id: 'user123', name: 'user@example.com', displayName: 'User' },
          pubKeyCredParams: [{ alg: -7, type: 'public-key' }]
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.getPasskeyRegistrationOptions(options);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/register/options', options);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('verifyPasskeyRegistration', () => {
      it('should verify passkey registration successfully', async () => {
        const credential = {
          id: 'credential_id_123',
          rawId: 'raw_credential_id',
          type: 'public-key' as const,
          response: {
            clientDataJSON: 'client_data',
            attestationObject: 'attestation_object'
          }
        };
        const mockResponse = {
          passkey: {
            id: '550e8400-e29b-41d4-a716-446655440000',
            name: 'My Passkey',
            created_at: '2023-01-01T00:00:00Z'
          },
          message: 'Passkey registered successfully'
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.verifyPasskeyRegistration(credential);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/register/verify', {
          credential: credential,
          name: undefined
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('getPasskeyAuthenticationOptions', () => {
      it('should get passkey authentication options successfully', async () => {
        const email = 'user@example.com';
        const mockResponse = {
          sessionId: 'sess_abc123',
          challenge: 'auth_challenge_123',
          rpId: 'app.example.com',
          timeout: 60000,
          userVerification: 'preferred',
          allowCredentials: [
            {
              id: 'credential_id_123',
              type: 'public-key'
            }
          ]
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.getPasskeyAuthenticationOptions(email);

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/authenticate/options', {
          email: email
        }, {
          skipAuth: true
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('verifyPasskeyAuthentication', () => {
      it('should verify passkey authentication successfully', async () => {
        const credential = {
          id: 'credential_id_123',
          rawId: 'raw_credential_id',
          type: 'public-key' as const,
          response: {
            clientDataJSON: 'client_data',
            authenticatorData: 'authenticator_data',
            signature: 'signature'
          }
        };
        // Flat token response + partial user, and session_id as a query param.
        const mockResponse = {
          verified: true,
          access_token: tokenFixtures.validAccessToken,
          refresh_token: tokenFixtures.validRefreshToken,
          token_type: 'bearer' as const,
          expires_in: 3600,
          user: {
            id: userFixtures.validUser.id,
            email: userFixtures.validUser.email,
            first_name: userFixtures.validUser.first_name,
            last_name: userFixtures.validUser.last_name
          }
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.verifyPasskeyAuthentication(credential, 'sess_abc123', 'user@example.com');

        expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/authenticate/verify', {
          credential: credential,
          email: 'user@example.com'
        }, { skipAuth: true, params: { session_id: 'sess_abc123' } });
        expect(result).toEqual(mockResponse);
        expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
          access_token: mockResponse.access_token,
          refresh_token: mockResponse.refresh_token,
          expires_at: expect.any(Number)
        });
        expect(mockOnSignIn).toHaveBeenCalled();
      });
    });

    describe('listPasskeys', () => {
      it('should list user passkeys successfully', async () => {
        const mockResponse = [
          {
            id: '550e8400-e29b-41d4-a716-446655440000',
            name: 'iPhone Touch ID',
            created_at: '2023-01-01T00:00:00Z',
            last_used_at: '2023-01-15T00:00:00Z'
          },
          {
            id: 'passkey_456',
            name: 'Security Key',
            created_at: '2023-01-10T00:00:00Z',
            last_used_at: null
          }
        ];

        mockHttpClient.get.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.listPasskeys();

        expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/passkeys/');
        expect(result).toEqual(mockResponse);
      });
    });

    describe('updatePasskey', () => {
      it('should update passkey name successfully', async () => {
        const passkeyId = '550e8400-e29b-41d4-a716-446655440000';
        const name = 'Updated Passkey Name';
        const mockResponse = {
          id: '550e8400-e29b-41d4-a716-446655440000',
          name: 'Updated Passkey Name',
          created_at: '2023-01-01T00:00:00Z',
          last_used_at: '2023-01-15T00:00:00Z'
        };

        mockHttpClient.patch.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.updatePasskey(passkeyId, name);

        expect(mockHttpClient.patch).toHaveBeenCalledWith(`/api/v1/passkeys/${passkeyId}`, {
          name: name
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('deletePasskey', () => {
      it('should delete passkey successfully', async () => {
        const passkeyId = '550e8400-e29b-41d4-a716-446655440001';
        const password = 'userpassword123';
        const mockResponse = { message: 'Passkey deleted successfully' };

        mockHttpClient.delete.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.deletePasskey(passkeyId, password);

        expect(mockHttpClient.delete).toHaveBeenCalledWith(`/api/v1/passkeys/${passkeyId}`, {
          data: { password: password }
        });
        expect(result).toEqual(mockResponse);
      });
    });

    describe('regeneratePasskeySecret', () => {
      it('should regenerate passkey secret successfully', async () => {
        const passkeyId = '550e8400-e29b-41d4-a716-446655440002';
        const mockResponse = {
          id: '550e8400-e29b-41d4-a716-446655440000',
          name: 'iPhone Touch ID',
          created_at: '2023-01-01T00:00:00Z',
          last_used_at: '2023-01-15T00:00:00Z'
        };

        mockHttpClient.post.mockResolvedValue({
          data: mockResponse
        });

        const result = await auth.regeneratePasskeySecret(passkeyId);

        expect(mockHttpClient.post).toHaveBeenCalledWith(`/api/v1/passkeys/${passkeyId}/regenerate-secret`);
        expect(result).toEqual(mockResponse);
      });
    });
  });
});
