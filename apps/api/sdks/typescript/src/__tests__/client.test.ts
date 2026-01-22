/**
 * Tests for Janua TypeScript SDK Client
 */

import { JanuaClient, createClient } from '../index';
import { APIStatus } from '../types/base';
import { AuthenticationError, ValidationError } from '../errors';

// Mock axios to avoid real HTTP requests
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    request: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() }
    }
  })),
  isAxiosError: jest.fn()
}));

describe('JanuaClient', () => {
  let client: JanuaClient;

  beforeEach(() => {
    client = createClient({
      base_url: 'https://api.test.janua.dev',
      debug: true
    });
  });

  describe('Client Creation', () => {
    it('should create client with default configuration', () => {
      const defaultClient = new JanuaClient({});
      expect(defaultClient).toBeInstanceOf(JanuaClient);
    });

    it('should create client with custom configuration', () => {
      const customClient = new JanuaClient({
        base_url: 'https://custom.api.com',
        timeout: 60000,
        debug: true
      });
      expect(customClient).toBeInstanceOf(JanuaClient);
    });

    it('should create client using factory function', () => {
      const factoryClient = createClient({
        base_url: 'https://factory.api.com',
        api_key: 'test-key'
      });
      expect(factoryClient).toBeInstanceOf(JanuaClient);
    });
  });

  describe('Authentication Methods', () => {
    it('should handle successful login', async () => {
      const mockResponse = {
        status: APIStatus.SUCCESS,
        message: 'Login successful',
        data: {
          user: {
            id: 'user-123',
            email: 'test@example.com',
            name: 'Test User',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          access_token: 'mock-access-token',
          token_type: 'Bearer',
          expires_in: 3600,
          refresh_token: 'mock-refresh-token'
        }
      };

      // Mock the HTTP request
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({ data: mockResponse });

      const result = await client.login({
        email: 'test@example.com',
        password: 'password123'
      });

      expect(result.status).toBe(APIStatus.SUCCESS);
      expect(result.data.user.email).toBe('test@example.com');
      expect(result.data.access_token).toBe('mock-access-token');
    });

    it('should handle login failure', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockRejectedValue({
        response: {
          status: 401,
          data: {
            status: APIStatus.ERROR,
            message: 'Invalid credentials',
            error_code: 'INVALID_CREDENTIALS'
          }
        }
      });

      await expect(client.login({
        email: 'test@example.com',
        password: 'wrong-password'
      })).rejects.toThrow(AuthenticationError);
    });

    it('should handle registration with validation errors', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockRejectedValue({
        response: {
          status: 422,
          data: {
            status: APIStatus.ERROR,
            message: 'Validation failed',
            error_code: 'VALIDATION_ERROR',
            validation_errors: [
              {
                field: 'email',
                message: 'Email is already registered',
                code: 'EMAIL_EXISTS'
              },
              {
                field: 'password',
                message: 'Password must be at least 8 characters',
                code: 'PASSWORD_TOO_SHORT'
              }
            ]
          }
        }
      });

      try {
        await client.register({
          email: 'existing@example.com',
          password: '123',
          name: 'Test User',
          terms_accepted: true
        });
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError);
        const validationError = error as ValidationError;
        expect(validationError.validation_errors).toHaveLength(2);
        expect(validationError.getFieldErrors('email')).toHaveLength(1);
        expect(validationError.getAllFields()).toContain('email');
        expect(validationError.getAllFields()).toContain('password');
      }
    });
  });

  describe('Token Management', () => {
    it('should check authentication status', async () => {
      // Mock token manager
      const mockTokenManager = client['token_manager'] as any;
      mockTokenManager.isAuthenticated = jest.fn().mockResolvedValue(true);

      const isAuth = await client.isAuthenticated();
      expect(isAuth).toBe(true);
    });

    it('should handle logout', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({
        data: { status: APIStatus.SUCCESS, message: 'Logged out successfully' }
      });

      const mockTokenManager = client['token_manager'] as any;
      mockTokenManager.clearTokens = jest.fn().mockResolvedValue(undefined);

      await client.logout();

      expect(mockTokenManager.clearTokens).toHaveBeenCalled();
    });
  });

  describe('User Management', () => {
    it('should get current user profile', async () => {
      const mockProfile = {
        status: APIStatus.SUCCESS,
        message: 'User profile retrieved',
        data: {
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
          avatar_url: 'https://example.com/avatar.jpg',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      };

      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({ data: mockProfile });

      const result = await client.getCurrentUser();
      expect(result.data.email).toBe('test@example.com');
      expect(result.data.name).toBe('Test User');
    });

    it('should update user profile', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({
        data: {
          status: APIStatus.SUCCESS,
          message: 'Profile updated',
          data: {
            id: 'user-123',
            email: 'test@example.com',
            name: 'Updated Name',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        }
      });

      const result = await client.updateProfile({
        name: 'Updated Name'
      });

      expect(result.data.name).toBe('Updated Name');
    });
  });

  describe('Organization Management', () => {
    it('should create organization', async () => {
      const mockOrg = {
        status: APIStatus.SUCCESS,
        message: 'Organization created',
        data: {
          id: 'org-123',
          name: 'Test Org',
          slug: 'test-org',
          description: 'Test organization',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      };

      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({ data: mockOrg });

      const result = await client.createOrganization({
        name: 'Test Org',
        slug: 'test-org',
        description: 'Test organization'
      });

      expect(result.data.name).toBe('Test Org');
      expect(result.data.slug).toBe('test-org');
    });

    it('should list organizations', async () => {
      const mockOrgs = {
        status: APIStatus.SUCCESS,
        message: 'Organizations retrieved',
        data: [
          {
            id: 'org-1',
            name: 'Org 1',
            slug: 'org-1',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 'org-2',
            name: 'Org 2',
            slug: 'org-2',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ],
        pagination: {
          page: 1,
          size: 20,
          total: 2,
          pages: 1,
          has_prev: false,
          has_next: false
        }
      };

      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockResolvedValue({ data: mockOrgs });

      const result = await client.getOrganizations();
      expect(result.data).toHaveLength(2);
      expect(result.pagination.total).toBe(2);
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockRejectedValue(new Error('Network error'));

      await expect(client.getCurrentUser()).rejects.toThrow();
    });

    it('should handle rate limiting', async () => {
      const mockHttp = client['http'] as any;
      mockHttp.request = jest.fn().mockRejectedValue({
        response: {
          status: 429,
          data: {
            status: APIStatus.ERROR,
            message: 'Rate limit exceeded',
            error_code: 'RATE_LIMIT_EXCEEDED',
            retry_after: 60
          },
          headers: {
            'retry-after': '60'
          }
        }
      });

      try {
        await client.getCurrentUser();
      } catch (error: any) {
        expect(error.status_code).toBe(429);
      }
    });
  });
});

describe('createClient Factory', () => {
  it('should create client with API key authentication', () => {
    const client = createClient({
      api_key: 'test-api-key',
      base_url: 'https://api.test.com'
    });

    expect(client).toBeInstanceOf(JanuaClient);
  });

  it('should create client with JWT authentication when no API key', () => {
    const client = createClient({
      base_url: 'https://api.test.com'
    });

    expect(client).toBeInstanceOf(JanuaClient);
  });
});