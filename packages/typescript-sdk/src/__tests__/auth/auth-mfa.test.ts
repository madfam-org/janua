/**
 * Tests for MFA (Multi-Factor Authentication) operations
 */

import { Auth } from '../../auth';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { UserStatus } from '../../types';
import type { MFAParams } from '../../types';

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

describe('Auth - MFA Operations', () => {
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
        expires_in: 3600,
        token_type: 'bearer' as const
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
          refresh_token: mockResponse.refresh_token,
          expires_in: mockResponse.expires_in,
          token_type: mockResponse.token_type
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

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/regenerate-backup-codes', {
        password: password
      });
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

      expect(mockHttpClient.post).toHaveBeenCalledWith('/api/v1/mfa/validate-code', {
        code: code
      });
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
