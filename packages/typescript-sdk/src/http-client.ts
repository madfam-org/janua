/**
 * HTTP client for the Janua TypeScript SDK
 */

import type {
  RequestConfig,
  HttpResponse,
  RateLimitInfo,
  JanuaConfig
} from './types';
import {
  JanuaError,
  NetworkError,
  RateLimitError,
  ConfigurationError
} from './errors';
import { TokenManager, RetryUtils, EventEmitter } from './utils';
import type { SdkEventMap } from './types';

/**
 * HTTP client with automatic token refresh and retry logic
 */
export class HttpClient extends EventEmitter<SdkEventMap> {
  private config: Required<Pick<JanuaConfig, 'baseURL' | 'timeout' | 'retryAttempts' | 'retryDelay'>>;
  private tokenManager: TokenManager;
  private refreshPromise: Promise<void> | null = null;

  constructor(config: JanuaConfig, tokenManager: TokenManager) {
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
  async request<T = unknown>(config: RequestConfig): Promise<HttpResponse<T>> {
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

      const status = response.status ?? 200;
      const headers = response.headers ?? {};

      // Handle rate limiting
      if (status === 429) {
        const rateLimitInfo = this.parseRateLimitHeaders(headers);
        throw new RateLimitError('Rate limit exceeded', rateLimitInfo);
      }

      // Handle authentication errors
      if (status === 401 && !config.skipAuth) {
        await this.handleAuthError(config);
        // Retry the request with refreshed token
        return this.request(config);
      }

      // Handle API errors
      if (status >= 400) {
        await this.handleApiError(response);
      }

      return response as HttpResponse<T>;
    });
  }

  /**
   * Execute request with retry logic
   */
  private async executeWithRetry<T>(
    operation: () => Promise<T>
  ): Promise<T> {
    return RetryUtils.withRetry(operation, {
      maxAttempts: this.config.retryAttempts,
      initialDelay: this.config.retryDelay,
      backoffMultiplier: 2,
      maxDelay: 30000
    });
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
      let data: unknown;
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
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new NetworkError('Request timeout');
      }
      throw new NetworkError('Network request failed', error instanceof Error ? error : undefined);
    }
  }

  /**
   * Handle authentication errors
   */
  private async handleAuthError(_originalConfig: RequestConfig): Promise<void> {
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
      throw new JanuaError('No refresh token available', 'AUTHENTICATION_ERROR');
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

      this.emit('token:refreshed', { tokens: { ...response.data, token_type: 'bearer' as const } });
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
    let errorData: { error?: string; message?: string; detail?: string; details?: Record<string, unknown> };

    try {
      errorData = typeof response.data === 'string'
        ? { message: response.data }
        : (response.data as typeof errorData) || { message: 'Unknown error occurred' };
    } catch {
      errorData = { message: 'Unknown error occurred' };
    }

    const apiError = {
      error: errorData.error || 'API_ERROR',
      message: errorData.message || errorData.detail || 'An error occurred',
      details: errorData.details || {},
      status_code: response.status ?? 500
    };

    throw JanuaError.fromApiError(apiError);
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
    headers.forEach((value: string, key: string) => {
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
      return `janua-typescript-sdk/${sdkVersion} (Browser)`;
    } else if (typeof process !== 'undefined') {
      return `janua-typescript-sdk/${sdkVersion} (Node.js ${process.version})`;
    } else {
      return `janua-typescript-sdk/${sdkVersion}`;
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

  async post<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'POST',
      url,
      data,
      ...config
    });
  }

  async put<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'PUT',
      url,
      data,
      ...config
    });
  }

  async patch<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'PATCH',
      url,
      data,
      ...config
    });
  }

  async delete<T = unknown>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({
      method: 'DELETE',
      url,
      ...config
    });
  }
}

/** Axios instance type (minimal interface for dynamic import) */
interface AxiosInstance {
  interceptors: {
    request: { use: (onFulfilled: (config: AxiosRequestConfig) => Promise<AxiosRequestConfig>) => void };
    response: { use: (onFulfilled: (response: AxiosResponse) => AxiosResponse, onRejected: (error: AxiosError) => Promise<never>) => void };
  };
  get: <T>(url: string, config?: Partial<AxiosRequestConfig>) => Promise<AxiosResponse<T>>;
  post: <T>(url: string, data?: unknown, config?: Partial<AxiosRequestConfig>) => Promise<AxiosResponse<T>>;
  put: <T>(url: string, data?: unknown, config?: Partial<AxiosRequestConfig>) => Promise<AxiosResponse<T>>;
  patch: <T>(url: string, data?: unknown, config?: Partial<AxiosRequestConfig>) => Promise<AxiosResponse<T>>;
  delete: <T>(url: string, config?: Partial<AxiosRequestConfig>) => Promise<AxiosResponse<T>>;
  (config: AxiosRequestConfig): Promise<AxiosResponse>;
}

interface AxiosRequestConfig {
  url?: string;
  method?: string;
  baseURL?: string;
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  data?: unknown;
  timeout?: number;
  skipAuth?: boolean;
  _retry?: boolean;
}

interface AxiosResponse<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  config: AxiosRequestConfig;
}

interface AxiosError {
  config: AxiosRequestConfig;
  response?: AxiosResponse<{ error?: string; message?: string; detail?: string; details?: Record<string, unknown> }>;
  request?: unknown;
  message: string;
}

interface AxiosStatic {
  create: (config: { baseURL: string; timeout: number; headers: Record<string, string> }) => AxiosInstance;
}

/**
 * Axios adapter for environments that prefer axios
 */
export class AxiosHttpClient extends EventEmitter<SdkEventMap> {
  private axiosLib: AxiosStatic;
  private axios!: AxiosInstance;
  private tokenManager: TokenManager;
  private refreshPromise: Promise<void> | null = null;

  constructor(config: JanuaConfig, tokenManager: TokenManager) {
    super();

    this.tokenManager = tokenManager;

    try {
      // Try to import axios
      this.axiosLib = require('axios');
      this.setupAxiosInstance(config);
    } catch (error) {
      throw new ConfigurationError('Axios is not available. Please install axios or use the default fetch client.');
    }
  }

  private setupAxiosInstance(config: JanuaConfig): void {
    this.axios = this.axiosLib.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Request interceptor for auth
    this.axios.interceptors.request.use(async (axiosConfig: AxiosRequestConfig) => {
      if (!axiosConfig.skipAuth) {
        const accessToken = await this.tokenManager.getAccessToken();
        if (accessToken) {
          axiosConfig.headers = axiosConfig.headers || {};
          axiosConfig.headers.Authorization = `Bearer ${accessToken}`;
        }
      }
      return axiosConfig;
    });

    // Response interceptor for error handling
    this.axios.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error: AxiosError): Promise<never> => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.skipAuth) {
          originalRequest._retry = true;

          try {
            await this.handleAuthError();
            return this.axios(originalRequest) as never;
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
          throw JanuaError.fromApiError(apiError);
        } else if (error.request) {
          throw new NetworkError('Network request failed');
        } else {
          throw new NetworkError('Request setup failed');
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
      throw new JanuaError('No refresh token available', 'AUTHENTICATION_ERROR');
    }

    try {
      const response = await this.axios.post<{ access_token: string; refresh_token: string; expires_in: number }>('/api/v1/auth/refresh', {
        refresh_token: refreshToken
      }, { skipAuth: true });

      const expiresAt = Date.now() + (response.data.expires_in * 1000);
      await this.tokenManager.setTokens({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_at: expiresAt
      });

      this.emit('token:refreshed', { tokens: { ...response.data, token_type: 'bearer' as const } });
    } catch (error) {
      await this.tokenManager.clearTokens();
      this.emit('token:expired', {});
      this.emit('auth:signedOut', {});
      throw error;
    }
  }

  async request<T = unknown>(config: RequestConfig): Promise<HttpResponse<T>> {
    try {
      const response = await this.axios({
        method: config.method,
        url: config.url,
        data: config.data,
        params: config.params as Record<string, unknown>,
        headers: config.headers,
        timeout: config.timeout,
        skipAuth: config.skipAuth
      });

      return {
        data: response.data as T,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers
      };
    } catch (error) {
      throw error; // Already converted by interceptor
    }
  }

  // Convenience methods
  async get<T = unknown>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'GET', url, ...config });
  }

  async post<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'POST', url, data, ...config });
  }

  async put<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'PUT', url, data, ...config });
  }

  async patch<T = unknown>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'PATCH', url, data, ...config });
  }

  async delete<T = unknown>(url: string, config?: Partial<RequestConfig>): Promise<HttpResponse<T>> {
    return this.request<T>({ method: 'DELETE', url, ...config });
  }
}

/**
 * Factory function to create appropriate HTTP client
 */
export function createHttpClient(config: JanuaConfig, tokenManager: TokenManager): HttpClient | AxiosHttpClient {
  // Check if axios is available and preferred
  if (config.environment && config.environment !== 'browser' as any) {
    try {
      require.resolve('axios');
      return new AxiosHttpClient(config, tokenManager);
    } catch {
      // Axios not available, use fetch client
    }
  }

  return new HttpClient(config, tokenManager);
}
