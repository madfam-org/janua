/**
 * Tests for Passkey operations
 */

import { Auth } from '../../auth';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { UserStatus } from '../../types';

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

describe('Auth - Passkey Operations', () => {
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

    it('should verify passkey registration with name', async () => {
      const credential = {
        id: 'credential_id_123',
        rawId: 'raw_credential_id',
        type: 'public-key' as const,
        response: {
          clientDataJSON: 'client_data',
          attestationObject: 'attestation_object'
        }
      };
      const name = 'My iPhone';
      const mockResponse = {
        passkey: {
          id: '550e8400-e29b-41d4-a716-446655440000',
          name: 'My iPhone',
          created_at: '2023-01-01T00:00:00Z'
        },
        message: 'Passkey registered successfully'
      };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.verifyPasskeyRegistration(credential, name);

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/register/verify', {
        credential: credential,
        name: name
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getPasskeyAuthenticationOptions', () => {
    it('should get passkey authentication options successfully', async () => {
      const email = 'user@example.com';
      const mockResponse = {
        challenge: 'auth_challenge_123',
        allowCredentials: [
          {
            id: 'credential_id_123',
            type: 'public-key',
            transports: ['usb', 'nfc']
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
      const mockResponse = {
        user: userFixtures.validUser,
        tokens: tokenFixtures.validTokens,
        message: 'Passkey authentication successful'
      };

      mockHttpClient.post.mockResolvedValue({
        data: mockResponse
      });

      const result = await auth.verifyPasskeyAuthentication(credential, 'auth_challenge_123', 'user@example.com');

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/passkeys/authenticate/verify', {
        credential: credential,
        challenge: 'auth_challenge_123',
        email: 'user@example.com'
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
