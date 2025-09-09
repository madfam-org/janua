import { PlintoClient } from '../client';

describe('PlintoClient', () => {
  let client: PlintoClient;
  const mockFetch = jest.fn();
  
  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockClear();
    client = new PlintoClient({
      issuer: 'https://plinto.dev',
      clientId: 'test-client',
      redirectUri: 'http://localhost:3000/callback',
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('constructor', () => {
    it('should initialize with required config', () => {
      expect(client).toBeDefined();
      expect(client.issuer).toBe('https://plinto.dev');
      expect(client.clientId).toBe('test-client');
    });

    it('should throw error if config is missing', () => {
      expect(() => new PlintoClient({} as any)).toThrow();
    });

    it('should validate issuer URL format', () => {
      expect(() => new PlintoClient({
        issuer: 'not-a-url',
        clientId: 'test',
        redirectUri: 'http://localhost',
      })).toThrow('Invalid issuer URL');
    });
  });

  describe('signIn', () => {
    it('should call auth endpoint with credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'test-token',
          refresh_token: 'refresh-token',
          expires_in: 3600,
        }),
      });

      const result = await client.signIn({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/signin',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            email: 'test@example.com',
            password: 'password123',
          }),
        })
      );

      expect(result).toEqual({
        access_token: 'test-token',
        refresh_token: 'refresh-token',
        expires_in: 3600,
      });
    });

    it('should handle signin errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({
          error: 'Invalid credentials',
        }),
      });

      await expect(client.signIn({
        email: 'test@example.com',
        password: 'wrong',
      })).rejects.toThrow('Invalid credentials');
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(client.signIn({
        email: 'test@example.com',
        password: 'password',
      })).rejects.toThrow('Network error');
    });
  });

  describe('signUp', () => {
    it('should call signup endpoint with user data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'user-123',
          email: 'test@example.com',
          created_at: '2024-01-01T00:00:00Z',
        }),
      });

      const result = await client.signUp({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/signup',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'test@example.com',
            password: 'password123',
            name: 'Test User',
          }),
        })
      );

      expect(result).toEqual({
        id: 'user-123',
        email: 'test@example.com',
        created_at: '2024-01-01T00:00:00Z',
      });
    });

    it('should validate email format', async () => {
      await expect(client.signUp({
        email: 'invalid-email',
        password: 'password123',
      })).rejects.toThrow('Invalid email format');
    });

    it('should validate password strength', async () => {
      await expect(client.signUp({
        email: 'test@example.com',
        password: '123',
      })).rejects.toThrow('Password must be at least 8 characters');
    });
  });

  describe('signOut', () => {
    it('should call signout endpoint and clear tokens', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      client.setAccessToken('test-token');
      await client.signOut();

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/signout',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
          }),
        })
      );

      expect(client.getAccessToken()).toBeNull();
    });

    it('should handle signout without token', async () => {
      await expect(client.signOut()).rejects.toThrow('No active session');
    });
  });

  describe('refreshToken', () => {
    it('should refresh access token using refresh token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'new-token',
          expires_in: 3600,
        }),
      });

      client.setRefreshToken('refresh-token');
      const result = await client.refreshToken();

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/refresh',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            refresh_token: 'refresh-token',
          }),
        })
      );

      expect(result.access_token).toBe('new-token');
      expect(client.getAccessToken()).toBe('new-token');
    });

    it('should handle refresh token expiry', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({
          error: 'Refresh token expired',
        }),
      });

      client.setRefreshToken('expired-token');
      await expect(client.refreshToken()).rejects.toThrow('Refresh token expired');
    });
  });

  describe('getUser', () => {
    it('should fetch current user profile', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
        }),
      });

      client.setAccessToken('test-token');
      const user = await client.getUser();

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/users/me',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
          }),
        })
      );

      expect(user).toEqual({
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
      });
    });

    it('should require authentication', async () => {
      await expect(client.getUser()).rejects.toThrow('Authentication required');
    });
  });

  describe('updateUser', () => {
    it('should update user profile', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'user-123',
          name: 'Updated Name',
        }),
      });

      client.setAccessToken('test-token');
      const result = await client.updateUser({
        name: 'Updated Name',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/users/me',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            name: 'Updated Name',
          }),
        })
      );

      expect(result.name).toBe('Updated Name');
    });
  });

  describe('verifyEmail', () => {
    it('should verify email with token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          email_verified: true,
        }),
      });

      const result = await client.verifyEmail('verification-token');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/verify-email',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            token: 'verification-token',
          }),
        })
      );

      expect(result.email_verified).toBe(true);
    });

    it('should handle invalid verification token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          error: 'Invalid or expired token',
        }),
      });

      await expect(client.verifyEmail('bad-token'))
        .rejects.toThrow('Invalid or expired token');
    });
  });

  describe('resetPassword', () => {
    it('should request password reset', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Reset email sent',
        }),
      });

      const result = await client.resetPassword('test@example.com');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/reset-password',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'test@example.com',
          }),
        })
      );

      expect(result.success).toBe(true);
    });

    it('should confirm password reset with token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
        }),
      });

      const result = await client.confirmPasswordReset({
        token: 'reset-token',
        password: 'newpassword123',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/api/v1/auth/reset-password/confirm',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            token: 'reset-token',
            password: 'newpassword123',
          }),
        })
      );

      expect(result.success).toBe(true);
    });
  });

  describe('token management', () => {
    it('should store and retrieve access token', () => {
      client.setAccessToken('test-token');
      expect(client.getAccessToken()).toBe('test-token');
    });

    it('should store and retrieve refresh token', () => {
      client.setRefreshToken('refresh-token');
      expect(client.getRefreshToken()).toBe('refresh-token');
    });

    it('should clear all tokens', () => {
      client.setAccessToken('test-token');
      client.setRefreshToken('refresh-token');
      client.clearTokens();
      
      expect(client.getAccessToken()).toBeNull();
      expect(client.getRefreshToken()).toBeNull();
    });

    it('should check if authenticated', () => {
      expect(client.isAuthenticated()).toBe(false);
      
      client.setAccessToken('test-token');
      expect(client.isAuthenticated()).toBe(true);
      
      client.clearTokens();
      expect(client.isAuthenticated()).toBe(false);
    });
  });

  describe('interceptors', () => {
    it('should add auth header to requests when token exists', async () => {
      client.setAccessToken('test-token');
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: 'test' }),
      });

      await client.request('/test-endpoint');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://plinto.dev/test-endpoint',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
          }),
        })
      );
    });

    it('should retry with refresh token on 401', async () => {
      client.setAccessToken('expired-token');
      client.setRefreshToken('refresh-token');

      // First call returns 401
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ error: 'Token expired' }),
      });

      // Refresh call returns new token
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'new-token',
          expires_in: 3600,
        }),
      });

      // Retry call succeeds
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: 'success' }),
      });

      const result = await client.request('/protected');

      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(client.getAccessToken()).toBe('new-token');
      expect(result.data).toBe('success');
    });
  });

  describe('error handling', () => {
    it('should handle rate limiting', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers({
          'Retry-After': '60',
        }),
        json: async () => ({
          error: 'Rate limit exceeded',
        }),
      });

      await expect(client.request('/test'))
        .rejects.toThrow('Rate limit exceeded. Retry after 60 seconds');
    });

    it('should handle server errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          error: 'Internal server error',
        }),
      });

      await expect(client.request('/test'))
        .rejects.toThrow('Internal server error');
    });

    it('should handle network timeouts', async () => {
      mockFetch.mockImplementationOnce(() => 
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Network timeout')), 100)
        )
      );

      await expect(client.request('/test'))
        .rejects.toThrow('Network timeout');
    });
  });
});