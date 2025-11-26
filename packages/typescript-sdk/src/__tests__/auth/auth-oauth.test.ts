/**
 * Tests for OAuth operations
 */

import { Auth } from '../../auth';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { UserStatus, OAuthProvider } from '../../types';

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

describe('Auth - OAuth Operations', () => {
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

  describe('signInWithOAuth', () => {
    it('should initiate OAuth authorization', async () => {
      const params = {
        provider: 'google',
        redirect_uri: 'http://localhost:3000/auth/callback'
      };

      const mockResponse = {
        authorization_url: 'https://accounts.google.com/oauth/authorize?...'
      };

      mockHttpClient.get.mockResolvedValue({ data: mockResponse });

      const result = await auth.signInWithOAuth(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/authorize', {
        params
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getOAuthProviders', () => {
    it('should get OAuth providers successfully', async () => {
      const mockProviders = [
        {
          name: 'google',
          enabled: true,
          client_id: 'google_client_id'
        },
        {
          name: 'github',
          enabled: true,
          client_id: 'github_client_id'
        }
      ];

      mockHttpClient.get.mockResolvedValue({ data: { providers: mockProviders } });

      const result = await auth.getOAuthProviders();

      expect(mockHttpClient.get).toHaveBeenCalledWith('/api/v1/auth/oauth/providers', {
        skipAuth: true
      });
      expect(result).toEqual(mockProviders);
    });
  });

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
