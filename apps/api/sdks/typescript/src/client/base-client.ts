/**
 * Base HTTP client for Janua TypeScript SDK.
 *
 * Mirrors the architecture from app.sdk.client_base with TypeScript-specific
 * implementation using axios for HTTP requests.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import {
  ClientConfig,
  RequestOptions,
  AuthenticationMethod,
  RetryConfig
} from '../types/base';
import { TokenManager, MemoryTokenStorage, LocalStorageTokenStorage } from '../auth/token-manager';
import {
  SDKError,
  NetworkError,
  createErrorFromResponse
} from '../errors';

export abstract class BaseAPIClient {
  protected config: ClientConfig;
  protected http: AxiosInstance;
  protected token_manager: TokenManager;

  constructor(config: Partial<ClientConfig>) {
    this.config = this.buildConfig(config);
    this.http = this.createHttpClient();
    this.token_manager = this.createTokenManager();
  }

  /**
   * Build complete configuration with defaults
   */
  private buildConfig(config: Partial<ClientConfig>): ClientConfig {
    const default_retry_config: RetryConfig = {
      max_retries: 3,
      initial_delay_ms: 1000,
      max_delay_ms: 30000,
      backoff_factor: 2,
      retry_on_status_codes: [429, 502, 503, 504]
    };

    return {
      base_url: config.base_url || 'https://api.janua.dev',
      api_key: config.api_key,
      authentication_method: config.authentication_method || AuthenticationMethod.JWT_TOKEN,
      timeout: config.timeout || 30000,
      retry_config: { ...default_retry_config, ...config.retry_config },
      user_agent: config.user_agent || `janua-typescript-sdk/0.1.0`,
      debug: config.debug || false
    };
  }

  /**
   * Create configured axios instance
   */
  private createHttpClient(): AxiosInstance {
    const instance = axios.create({
      baseURL: this.config.base_url,
      timeout: this.config.timeout,
      headers: {
        'User-Agent': this.config.user_agent,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    // Request interceptor for authentication
    instance.interceptors.request.use(async (config) => {
      await this.addAuthenticationHeaders(config);
      return config;
    });

    // Response interceptor for error handling
    instance.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (axios.isAxiosError(error)) {
          // Handle rate limiting with retry logic
          if (error.response?.status === 429) {
            const retry_after = this.extractRetryAfter(error.response);
            if (retry_after && retry_after <= 60) { // Only retry if less than 60 seconds
              await this.sleep(retry_after * 1000);
              return instance.request(error.config!);
            }
          }

          // Convert axios error to SDK error
          throw this.createSDKError(error);
        }
        throw error;
      }
    );

    return instance;
  }

  /**
   * Create token manager based on environment
   */
  private createTokenManager(): TokenManager {
    // Use localStorage in browser, memory in Node.js
    const storage = typeof window !== 'undefined' && window.localStorage
      ? new LocalStorageTokenStorage()
      : new MemoryTokenStorage();

    return new TokenManager(storage, async (refresh_token) => {
      // Implement token refresh logic
      const response = await this.http.post('/api/v1/auth/refresh', {
        refresh_token
      });
      return response.data;
    });
  }

  /**
   * Add authentication headers to request
   */
  private async addAuthenticationHeaders(config: AxiosRequestConfig): Promise<void> {
    if (this.config.authentication_method === AuthenticationMethod.API_KEY && this.config.api_key) {
      config.headers = {
        ...config.headers,
        'X-API-Key': this.config.api_key
      };
    } else if (this.config.authentication_method === AuthenticationMethod.JWT_TOKEN) {
      const auth_header = await this.token_manager.getAuthorizationHeader();
      if (auth_header) {
        config.headers = {
          ...config.headers,
          'Authorization': auth_header
        };
      }
    }
  }

  /**
   * Make HTTP request with retry logic
   */
  protected async makeRequest<T = any>(
    method: string,
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: method.toLowerCase() as any,
      url: endpoint,
      timeout: options.timeout || this.config.timeout,
      headers: options.headers,
      params: options.query_params
    };

    if (method.toLowerCase() !== 'get' && options.headers?.['Content-Type'] !== 'multipart/form-data') {
      config.data = options.query_params;
      delete config.params;
    }

    let last_error: Error | null = null;
    const max_retries = options.retries ?? this.config.retry_config.max_retries;

    for (let attempt = 0; attempt <= max_retries; attempt++) {
      try {
        if (this.config.debug) {
          console.log(`[Janua SDK] ${method.toUpperCase()} ${endpoint} (attempt ${attempt + 1})`);
        }

        const response = await this.http.request(config);
        return this.processResponse<T>(response);
      } catch (error) {
        last_error = error as Error;

        // Don't retry on last attempt or non-retryable errors
        if (attempt === max_retries || !this.shouldRetry(error as any)) {
          break;
        }

        // Calculate delay for exponential backoff
        const delay = Math.min(
          this.config.retry_config.initial_delay_ms * Math.pow(this.config.retry_config.backoff_factor, attempt),
          this.config.retry_config.max_delay_ms
        );

        if (this.config.debug) {
          console.log(`[Janua SDK] Retrying after ${delay}ms...`);
        }

        await this.sleep(delay);
      }
    }

    throw last_error;
  }

  /**
   * Process successful HTTP response
   */
  private processResponse<T>(response: AxiosResponse): T {
    const data = response.data;

    // Check for error status in response body
    if (data.status === 'error') {
      throw createErrorFromResponse(data, response.status, data.request_id);
    }

    return data;
  }

  /**
   * Create SDK error from axios error
   */
  private createSDKError(error: any): SDKError {
    if (error.response) {
      // Server responded with error status
      const response_data = error.response.data;
      return createErrorFromResponse(response_data, error.response.status);
    } else if (error.request) {
      // Network error (no response received)
      return new NetworkError('Network request failed', error);
    } else {
      // Request setup error
      return new NetworkError('Request configuration error', error);
    }
  }

  /**
   * Check if error should be retried
   */
  private shouldRetry(error: any): boolean {
    if (!error.response) {
      // Retry network errors
      return true;
    }

    const status = error.response.status;
    return this.config.retry_config.retry_on_status_codes.includes(status);
  }

  /**
   * Extract retry-after header value
   */
  private extractRetryAfter(response: AxiosResponse): number | null {
    const retry_after = response.headers['retry-after'];
    if (!retry_after) return null;

    const seconds = parseInt(retry_after, 10);
    return isNaN(seconds) ? null : seconds;
  }

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Convenience methods for common HTTP operations
  protected async get<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.makeRequest<T>('GET', endpoint, options);
  }

  protected async post<T = any>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.makeRequest<T>('POST', endpoint, {
      ...options,
      query_params: data
    });
  }

  protected async put<T = any>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.makeRequest<T>('PUT', endpoint, {
      ...options,
      query_params: data
    });
  }

  protected async patch<T = any>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.makeRequest<T>('PATCH', endpoint, {
      ...options,
      query_params: data
    });
  }

  protected async delete<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.makeRequest<T>('DELETE', endpoint, options);
  }

  // Authentication methods
  public async authenticate(email: string, password: string): Promise<void> {
    const response = await this.post('/api/v1/auth/login', {
      email,
      password
    });

    await this.token_manager.storeTokenResponse(response.data);
  }

  public async logout(): Promise<void> {
    try {
      await this.post('/api/v1/auth/logout');
    } finally {
      await this.token_manager.clearTokens();
    }
  }

  public async isAuthenticated(): Promise<boolean> {
    return this.token_manager.isAuthenticated();
  }
}