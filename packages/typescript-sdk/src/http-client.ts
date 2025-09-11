/**
 * HTTP client for the Plinto TypeScript SDK
 */

import type {
  RequestConfig,
  HttpResponse,
  RateLimitInfo,
  PlintoConfig
} from './types';
import {
  PlintoError,
  NetworkError,
  RateLimitError,
  ErrorHandler
} from './errors';
import { TokenManager, RetryUtils, EventEmitter } from './utils';
import type { SdkEventMap } from './types';

/**
 * HTTP client with automatic token refresh and retry logic
 */
export class HttpClient extends EventEmitter<SdkEventMap> {
  private config: Required<Pick<PlintoConfig, 'baseURL' | 'timeout' | 'retryAttempts' | 'retryDelay'>>;
  private tokenManager: TokenManager;
  private refreshPromise: Promise<void> | null = null;

  constructor(config: PlintoConfig, tokenManager: TokenManager) {
    super();
    
    this.config = {
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      retryAttempts: config.retryAttempts || 3,
      retryDelay: config.retryDelay || 1000
    };
    
    this.tokenManager = tokenManager;
  }

  /**
   * Make HTTP request with automatic token handling
   */
  async request<T = any>(config: RequestConfig): Promise<HttpResponse<T>> {
    return this.executeWithRetry(async () => {
      // Add authorization header if not skipped and token exists
      if (!config.skipAuth) {
        const accessToken = await this.tokenManager.getAccessToken();
        if (accessToken) {
          config.headers = {
            ...config.headers,
            Authorization: `Bearer ${accessToken}`
          };
        }
      }

      // Build full URL
      const url = this.buildUrl(config.url, config.params);

      // Make request
      const response = await this.makeRequest(url, config);

      // Handle rate limiting
      if (response.status === 429) {
        const rateLimitInfo = this.parseRateLimitHeaders(response.headers);
        throw new RateLimitError('Rate limit exceeded', { rateLimitInfo });
      }

      // Handle authentication errors
      if (response.status === 401 && !config.skipAuth) {
        await this.handleAuthError(config);
        // Retry the request with refreshed token
        return this.request(config);
      }

      // Handle API errors
      if (response.status >= 400) {
        await this.handleApiError(response);
      }

      return response;
    });
  }

  /**
   * Execute request with retry logic
   */
  private async executeWithRetry<T>(
    operation: () => Promise<T>
  ): Promise<T> {
    return RetryUtils.withRetry(
      operation,
      this.config.retryAttempts,
      this.config.retryDelay,
      2, // backoff factor
      30000 // max delay
    );
  }

  /**
   * Build full URL with query parameters
   */
  private buildUrl(path: string, params?: Record<string, any>): string {
    const url = new URL(path, this.config.baseURL);
    
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          if (Array.isArray(value)) {
            value.forEach(v => url.searchParams.append(key, String(v)));
          } else {
            url.searchParams.set(key, String(value));
          }
        }
      });
    }
    
    return url.toString();
  }

  /**
   * Make the actual HTTP request
   */
  private async makeRequest(url: string, config: RequestConfig): Promise<HttpResponse> {
    const requestInit: RequestInit = {
      method: config.method,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': this.getUserAgent(),
        ...config.headers
      },
      signal: this.createAbortSignal(config.timeout || this.config.timeout)
    };

    if (config.data && config.method !== 'GET' && config.method !== 'DELETE') {
      requestInit.body = JSON.stringify(config.data);
    }

    try {
      const response = await fetch(url, requestInit);
      
      // Parse response
      let data: any;
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        const text = await response.text();
        data = text ? JSON.parse(text) : null;
      } else {
        data = await response.text();
      }

      return {
        data,
        status: response.status,
        statusText: response.statusText,
        headers: this.headersToObject(response.headers)
      };
    } catch (error: any) {
      if (error.name === 'AbortError') {
        throw new NetworkError('Request timeout');
      }
      throw new NetworkError('Network request failed', error);
    }
  }

  /**
   * Handle authentication errors
   */
  private async handleAuthError(originalConfig: RequestConfig): Promise<void> {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      await this.refreshPromise;
      return;
    }

    try {
      this.refreshPromise = this.refreshTokens();
      await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }

  /**
   * Refresh access tokens
   */
  private async refreshTokens(): Promise<void> {
    const refreshToken = await this.tokenManager.getRefreshToken();
    
    if (!refreshToken) {
      this.emit('auth:signedOut', {});
      throw new PlintoError('No refresh token available', 'AUTHENTICATION_ERROR');
    }

    try {
      const response = await this.request<{
        access_token: string;
        refresh_token: string;
        expires_in: number;
      }>({
        method: 'POST',
        url: '/api/v1/auth/refresh',
        data: { refresh_token: refreshToken },
        skipAuth: true
      });

      // Store new tokens
      const expiresAt = Date.now() + (response.data.expires_in * 1000);
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: expiresAt
      });

      this.emit('token:refreshed', { tokens: response.data });
    } catch (error) {
      // Clear tokens on refresh failure
      await this.tokenManager.clearTokens();
      this.emit('token:expired', {});
      this.emit('auth:signedOut', {});
      throw error;
    }
  }

  /**
   * Handle API errors
   */
  private async handleApiError(response: HttpResponse): Promise<never> {
    let errorData: any;
    
    try {
      errorData = typeof response.data === 'string' 
        ? { message: response.data }
        : response.data;
    } catch {
      errorData = { message: 'Unknown error occurred' };
    }

    const apiError = {
      error: errorData.error || 'API_ERROR',
      message: errorData.message || errorData.detail || 'An error occurred',
      details: errorData.details || {},
      status_code: response.status
    };

    throw PlintoError.fromApiError(apiError);
  }

  /**
   * Parse rate limit headers
   */
  private parseRateLimitHeaders(headers: Record<string, string>): RateLimitInfo {
    return {
      limit: parseInt(headers['x-ratelimit-limit'] || '0', 10),
      remaining: parseInt(headers['x-ratelimit-remaining'] || '0', 10),
      reset: parseInt(headers['x-ratelimit-reset'] || '0', 10),
      retry_after: parseInt(headers['retry-after'] || '0', 10) || undefined
    };
  }

  /**
   * Convert Headers object to plain object
   */
  private headersToObject(headers: Headers): Record<string, string> {
    const result: Record<string, string> = {};
    headers.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  }

  /**
   * Create abort signal for timeout
   */
  private createAbortSignal(timeout: number): AbortSignal {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), timeout);
    return controller.signal;
  }

  /**
   * Get user agent string
   */
  private getUserAgent(): string {
    const sdkVersion = '1.0.0'; // This should be dynamically set
    
    if (typeof window !== 'undefined') {
      return `plinto-typescript-sdk/${sdkVersion} (Browser)`;
    } else if (typeof process !== 'undefined') {
      return `plinto-typescript-sdk/${sdkVersion} (Node.js ${process.version})`;
    } else {
      return `plinto-typescript-sdk/${sdkVersion}`;
    }
  }

  /**
   * Convenience methods for different HTTP verbs
   */
  async get<T = any>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'GET',
      url,
      ...config
    });
  }

  async post<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'POST',
      url,
      data,
      ...config
    });
  }

  async put<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'PUT',
      url,
      data,
      ...config
    });
  }

  async patch<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'PATCH',
      url,
      data,
      ...config
    });
  }

  async delete<T = any>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'DELETE',
      url,
      ...config
    });
  }
}

/**
 * Axios adapter for environments that prefer axios
 */
export class AxiosHttpClient extends EventEmitter<SdkEventMap> {
  private axios: any;
  private tokenManager: TokenManager;
  private refreshPromise: Promise<void> | null = null;

  constructor(config: PlintoConfig, tokenManager: TokenManager) {
    super();
    
    this.tokenManager = tokenManager;
    
    try {
      // Try to import axios
      this.axios = require('axios');
      this.setupAxiosInstance(config);
    } catch (error) {
      throw new Error('Axios is not available. Please install axios or use the default fetch client.');
    }
  }

  private setupAxiosInstance(config: PlintoConfig): void {
    this.axios = this.axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Request interceptor for auth
    this.axios.interceptors.request.use(async (axiosConfig: any) => {
      if (!axiosConfig.skipAuth) {
        const accessToken = await this.tokenManager.getAccessToken();
        if (accessToken) {
          axiosConfig.headers.Authorization = `Bearer ${accessToken}`;
        }
      }
      return axiosConfig;
    });

    // Response interceptor for error handling
    this.axios.interceptors.response.use(
      (response: any) => response,
      async (error: any) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.skipAuth) {
          originalRequest._retry = true;
          
          try {
            await this.handleAuthError();
            return this.axios(originalRequest);
          } catch (refreshError) {
            return Promise.reject(refreshError);
          }
        }

        // Convert axios error to our error format
        if (error.response) {
          const apiError = {
            error: error.response.data?.error || 'API_ERROR',
            message: error.response.data?.message || error.response.data?.detail || error.message,
            details: error.response.data?.details || {},
            status_code: error.response.status
          };
          throw PlintoError.fromApiError(apiError);
        } else if (error.request) {
          throw new NetworkError('Network request failed', error);
        } else {
          throw new NetworkError('Request setup failed', error);
        }
      }
    );
  }

  private async handleAuthError(): Promise<void> {
    if (this.refreshPromise) {
      await this.refreshPromise;
      return;
    }

    try {
      this.refreshPromise = this.refreshTokens();
      await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async refreshTokens(): Promise<void> {
    const refreshToken = await this.tokenManager.getRefreshToken();
    
    if (!refreshToken) {
      this.emit('auth:signedOut', {});
      throw new PlintoError('No refresh token available', 'AUTHENTICATION_ERROR');
    }

    try {
      const response = await this.axios.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken
      }, { skipAuth: true });

      const expiresAt = Date.now() + (response.data.expires_in * 1000);
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: expiresAt
      });

      this.emit('token:refreshed', { tokens: response.data });
    } catch (error) {
      await this.tokenManager.clearTokens();
      this.emit('token:expired', {});
      this.emit('auth:signedOut', {});
      throw error;
    }
  }

  async request<T = any>(config: RequestConfig): Promise<HttpResponse<T>> {
    try {
      const response = await this.axios({
        method: config.method,
        url: config.url,
        data: config.data,
        params: config.params,
        headers: config.headers,
        timeout: config.timeout,
        skipAuth: config.skipAuth
      });

      return {
        data: response.data,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers
      };
    } catch (error) {
      throw error; // Already converted by interceptor
    }
  }

  // Convenience methods
  async get<T = any>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'GET', url, ...config });
  }

  async post<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'POST', url, data, ...config });
  }

  async put<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'PUT', url, data, ...config });
  }

  async patch<T = any>(url: string, data?: any, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'PATCH', url, data, ...config });
  }

  async delete<T = any>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'DELETE', url, ...config });
  }
}

/**
 * Factory function to create appropriate HTTP client
 */
export function createHttpClient(config: PlintoConfig, tokenManager: TokenManager): HttpClient | AxiosHttpClient {
  // Check if axios is available and preferred
  if (config.environment !== 'browser') {
    try {
      require.resolve('axios');
      return new AxiosHttpClient(config, tokenManager);
    } catch {
      // Axios not available, use fetch client
    }
  }
  
  return new HttpClient(config, tokenManager);
}