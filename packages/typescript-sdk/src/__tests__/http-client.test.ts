/**
 * Tests for HTTP Client
 */

import { HttpClient, AxiosHttpClient, createHttpClient } from '../http-client';
import { NetworkError, RateLimitError, ServerError, AuthenticationError } from '../errors';
import axios, { AxiosInstance, AxiosError } from 'axios';

jest.mock('axios');

describe('HttpClient', () => {
  describe('createHttpClient', () => {
    it('should create axios client when axios is available', () => {
      const config = {
        baseURL: 'https://api.example.com',
        headers: { 'X-Custom': 'header' },
        timeout: 5000
      };

      const client = createHttpClient(config);

      expect(client).toBeInstanceOf(AxiosHttpClient);
    });

    it('should throw error when no HTTP client is available', () => {
      const originalAxios = (global as any).axios;
      delete (global as any).axios;

      expect(() => createHttpClient({})).toThrow('No HTTP client available');

      (global as any).axios = originalAxios;
    });
  });
});

describe('AxiosHttpClient', () => {
  let client: AxiosHttpClient;
  let mockAxiosInstance: jest.Mocked<AxiosInstance>;
  let mockTokenManager: any;

  beforeEach(() => {
    jest.clearAllMocks();

    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() }
      },
      defaults: {
        headers: {
          common: {}
        }
      }
    } as any;

    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);

    mockTokenManager = {
      getAccessToken: jest.fn(),
      getRefreshToken: jest.fn(),
      setTokens: jest.fn(),
      clearTokens: jest.fn()
    };

    client = new AxiosHttpClient({
      baseURL: 'https://api.example.com',
      timeout: 5000
    });
  });

  describe('constructor', () => {
    it('should create axios instance with config', () => {
      expect(axios.create).toHaveBeenCalledWith({
        baseURL: 'https://api.example.com',
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });
    });

    it('should set up interceptors', () => {
      expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalled();
      expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalled();
    });

    it('should merge custom headers', () => {
      client = new AxiosHttpClient({
        baseURL: 'https://api.example.com',
        headers: {
          'X-Custom-Header': 'custom-value'
        }
      });

      expect(axios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Custom-Header': 'custom-value',
            'Content-Type': 'application/json'
          })
        })
      );
    });
  });

  describe('setTokenManager', () => {
    it('should set token manager', () => {
      client.setTokenManager(mockTokenManager);
      expect((client as any).tokenManager).toBe(mockTokenManager);
    });
  });

  describe('setAuthToken', () => {
    it('should set authorization header', () => {
      const token = 'test-token-123';
      client.setAuthToken(token);

      expect(mockAxiosInstance.defaults.headers.common['Authorization']).toBe(`Bearer ${token}`);
    });

    it('should remove authorization header when token is null', () => {
      client.setAuthToken('test-token');
      client.setAuthToken(null);

      expect(mockAxiosInstance.defaults.headers.common['Authorization']).toBeUndefined();
    });
  });

  describe('HTTP methods', () => {
    describe('get', () => {
      it('should make GET request', async () => {
        const mockResponse = { data: { result: 'success' } };
        mockAxiosInstance.get.mockResolvedValue(mockResponse);

        const result = await client.get('/users');

        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/users', undefined);
        expect(result).toEqual(mockResponse);
      });

      it('should make GET request with config', async () => {
        const mockResponse = { data: { result: 'success' } };
        mockAxiosInstance.get.mockResolvedValue(mockResponse);

        const config = { params: { page: 1 }, headers: { 'X-Custom': 'header' } };
        const result = await client.get('/users', config);

        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/users', config);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('post', () => {
      it('should make POST request', async () => {
        const mockResponse = { data: { id: '123' } };
        const postData = { name: 'Test User' };
        mockAxiosInstance.post.mockResolvedValue(mockResponse);

        const result = await client.post('/users', postData);

        expect(mockAxiosInstance.post).toHaveBeenCalledWith('/users', postData, undefined);
        expect(result).toEqual(mockResponse);
      });

      it('should make POST request with config', async () => {
        const mockResponse = { data: { id: '123' } };
        const postData = { name: 'Test User' };
        const config = { headers: { 'X-Custom': 'header' } };
        mockAxiosInstance.post.mockResolvedValue(mockResponse);

        const result = await client.post('/users', postData, config);

        expect(mockAxiosInstance.post).toHaveBeenCalledWith('/users', postData, config);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('put', () => {
      it('should make PUT request', async () => {
        const mockResponse = { data: { updated: true } };
        const putData = { name: 'Updated User' };
        mockAxiosInstance.put.mockResolvedValue(mockResponse);

        const result = await client.put('/users/123', putData);

        expect(mockAxiosInstance.put).toHaveBeenCalledWith('/users/123', putData, undefined);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('delete', () => {
      it('should make DELETE request', async () => {
        const mockResponse = { data: { deleted: true } };
        mockAxiosInstance.delete.mockResolvedValue(mockResponse);

        const result = await client.delete('/users/123');

        expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/users/123', undefined);
        expect(result).toEqual(mockResponse);
      });
    });

    describe('patch', () => {
      it('should make PATCH request', async () => {
        const mockResponse = { data: { patched: true } };
        const patchData = { status: 'active' };
        mockAxiosInstance.patch.mockResolvedValue(mockResponse);

        const result = await client.patch('/users/123', patchData);

        expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/users/123', patchData, undefined);
        expect(result).toEqual(mockResponse);
      });
    });
  });

  describe('Error handling', () => {
    it('should handle network errors', async () => {
      const networkError = new Error('Network Error');
      (networkError as any).code = 'ENOTFOUND';
      mockAxiosInstance.get.mockRejectedValue(networkError);

      await expect(client.get('/users')).rejects.toThrow(NetworkError);
    });

    it('should handle 401 authentication errors', async () => {
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 401,
          data: { message: 'Unauthorized' },
          statusText: 'Unauthorized',
          headers: {},
          config: {} as any
        },
        isAxiosError: true
      };
      mockAxiosInstance.get.mockRejectedValue(axiosError);

      await expect(client.get('/users')).rejects.toThrow(AuthenticationError);
    });

    it('should handle 429 rate limit errors', async () => {
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 429,
          data: { 
            message: 'Rate limit exceeded',
            retry_after: 60
          },
          headers: {
            'retry-after': '60',
            'x-ratelimit-limit': '100',
            'x-ratelimit-remaining': '0',
            'x-ratelimit-reset': '1234567890'
          },
          statusText: 'Too Many Requests',
          config: {} as any
        },
        isAxiosError: true
      };
      mockAxiosInstance.get.mockRejectedValue(axiosError);

      try {
        await client.get('/users');
        fail('Should have thrown RateLimitError');
      } catch (error) {
        expect(error).toBeInstanceOf(RateLimitError);
        expect((error as RateLimitError).rateLimitInfo).toEqual({
          limit: 100,
          remaining: 0,
          reset: 1234567890,
          retry_after: 60
        });
      }
    });

    it('should handle 500 server errors', async () => {
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 500,
          data: { message: 'Internal Server Error' },
          statusText: 'Internal Server Error',
          headers: {},
          config: {} as any
        },
        isAxiosError: true
      };
      mockAxiosInstance.get.mockRejectedValue(axiosError);

      await expect(client.get('/users')).rejects.toThrow(ServerError);
    });

    it('should handle timeout errors', async () => {
      const timeoutError = new Error('timeout of 5000ms exceeded');
      (timeoutError as any).code = 'ECONNABORTED';
      mockAxiosInstance.get.mockRejectedValue(timeoutError);

      await expect(client.get('/users')).rejects.toThrow(NetworkError);
    });
  });

  describe('Request interceptor', () => {
    let requestInterceptor: Function;

    beforeEach(() => {
      requestInterceptor = (mockAxiosInstance.interceptors.request.use as jest.Mock).mock.calls[0][0];
      client.setTokenManager(mockTokenManager);
    });

    it('should add auth token to requests', async () => {
      mockTokenManager.getAccessToken.mockResolvedValue('access-token-123');
      
      const config = { url: '/users', headers: {} };
      const result = await requestInterceptor(config);

      expect(result.headers['Authorization']).toBe('Bearer access-token-123');
    });

    it('should skip auth for skipAuth requests', async () => {
      const config = { url: '/public', headers: {}, skipAuth: true };
      const result = await requestInterceptor(config);

      expect(result.headers['Authorization']).toBeUndefined();
      expect(mockTokenManager.getAccessToken).not.toHaveBeenCalled();
    });

    it('should not add auth header if no token available', async () => {
      mockTokenManager.getAccessToken.mockResolvedValue(null);
      
      const config = { url: '/users', headers: {} };
      const result = await requestInterceptor(config);

      expect(result.headers['Authorization']).toBeUndefined();
    });
  });

  describe('Response interceptor', () => {
    let responseInterceptor: Function;
    let errorInterceptor: Function;

    beforeEach(() => {
      const interceptorCalls = (mockAxiosInstance.interceptors.response.use as jest.Mock).mock.calls[0];
      responseInterceptor = interceptorCalls[0];
      errorInterceptor = interceptorCalls[1];
      client.setTokenManager(mockTokenManager);
    });

    it('should pass through successful responses', () => {
      const response = { data: { success: true } };
      const result = responseInterceptor(response);

      expect(result).toBe(response);
    });

    it('should retry on 401 with refresh token', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue('refresh-token-123');
      mockAxiosInstance.post.mockResolvedValue({
        data: {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
          expires_in: 3600
        }
      });

      const originalRequest = { 
        url: '/users',
        _retry: false
      };
      
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 401,
          data: { message: 'Token expired' },
          statusText: 'Unauthorized',
          headers: {},
          config: originalRequest as any
        },
        config: originalRequest as any,
        isAxiosError: true
      };

      mockAxiosInstance.get.mockResolvedValue({ data: { users: [] } });

      const result = await errorInterceptor(axiosError);

      expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        expires_in: 3600
      });
      expect(mockAxiosInstance.defaults.headers.common['Authorization']).toBe('Bearer new-access-token');
    });

    it('should not retry if refresh fails', async () => {
      mockTokenManager.getRefreshToken.mockResolvedValue('refresh-token-123');
      mockAxiosInstance.post.mockRejectedValue(new Error('Refresh failed'));

      const originalRequest = { 
        url: '/users',
        _retry: false
      };
      
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 401,
          data: { message: 'Token expired' },
          statusText: 'Unauthorized',
          headers: {},
          config: originalRequest as any
        },
        config: originalRequest as any,
        isAxiosError: true
      };

      await expect(errorInterceptor(axiosError)).rejects.toThrow();
      expect(mockTokenManager.clearTokens).toHaveBeenCalled();
    });

    it('should not retry if already retried', async () => {
      const originalRequest = { 
        url: '/users',
        _retry: true
      };
      
      const axiosError: Partial<AxiosError> = {
        response: {
          status: 401,
          data: { message: 'Token expired' },
          statusText: 'Unauthorized',
          headers: {},
          config: originalRequest as any
        },
        config: originalRequest as any,
        isAxiosError: true
      };

      await expect(errorInterceptor(axiosError)).rejects.toThrow();
    });
  });

  describe('Event emitter', () => {
    it('should emit request events', async () => {
      const onSpy = jest.fn();
      client.on('request', onSpy);

      const mockResponse = { data: { result: 'success' } };
      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      await client.get('/users');

      expect(onSpy).toHaveBeenCalledWith({
        method: 'GET',
        url: '/users',
        config: undefined
      });
    });

    it('should emit response events', async () => {
      const onSpy = jest.fn();
      client.on('response', onSpy);

      const mockResponse = { data: { result: 'success' }, status: 200 };
      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      await client.get('/users');

      expect(onSpy).toHaveBeenCalledWith({
        method: 'GET',
        url: '/users',
        status: 200,
        data: { result: 'success' }
      });
    });

    it('should emit error events', async () => {
      const onSpy = jest.fn();
      client.on('error', onSpy);

      const error = new Error('Network error');
      mockAxiosInstance.get.mockRejectedValue(error);

      try {
        await client.get('/users');
      } catch {
        // Expected to throw
      }

      expect(onSpy).toHaveBeenCalledWith({
        method: 'GET',
        url: '/users',
        error
      });
    });

    it('should remove event listeners', () => {
      const onSpy = jest.fn();
      const unsubscribe = client.on('request', onSpy);
      
      unsubscribe();

      mockAxiosInstance.get.mockResolvedValue({ data: {} });
      client.get('/users');

      expect(onSpy).not.toHaveBeenCalled();
    });
  });
});