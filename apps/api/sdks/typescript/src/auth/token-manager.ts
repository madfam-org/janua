/**
 * Token management system for Janua TypeScript SDK.
 *
 * Mirrors the authentication patterns from app.sdk.authentication
 * with platform-appropriate TypeScript implementation.
 */

import { TokenResponse } from '../types/base';
import { AuthenticationError } from '../errors';

export interface TokenStorage {
  getToken(key: string): Promise<string | null>;
  setToken(key: string, value: string, expires_at?: Date): Promise<void>;
  removeToken(key: string): Promise<void>;
  clear(): Promise<void>;
}

/**
 * In-memory token storage (default, not persistent)
 */
export class MemoryTokenStorage implements TokenStorage {
  private tokens: Map<string, { value: string; expires_at?: Date }> = new Map();

  public async getToken(key: string): Promise<string | null> {
    const stored = this.tokens.get(key);
    if (!stored) return null;

    // Check expiration
    if (stored.expires_at && stored.expires_at <= new Date()) {
      this.tokens.delete(key);
      return null;
    }

    return stored.value;
  }

  public async setToken(key: string, value: string, expires_at?: Date): Promise<void> {
    this.tokens.set(key, { value, expires_at });
  }

  public async removeToken(key: string): Promise<void> {
    this.tokens.delete(key);
  }

  public async clear(): Promise<void> {
    this.tokens.clear();
  }
}

/**
 * LocalStorage-based token storage (browser environment)
 */
export class LocalStorageTokenStorage implements TokenStorage {
  private prefix: string;

  constructor(prefix: string = 'janua_') {
    this.prefix = prefix;
  }

  public async getToken(key: string): Promise<string | null> {
    if (typeof localStorage === 'undefined') {
      throw new Error('LocalStorage is not available in this environment');
    }

    const fullKey = this.prefix + key;
    const stored = localStorage.getItem(fullKey);
    if (!stored) return null;

    try {
      const data = JSON.parse(stored);

      // Check expiration
      if (data.expires_at && new Date(data.expires_at) <= new Date()) {
        localStorage.removeItem(fullKey);
        return null;
      }

      return data.value;
    } catch {
      // Invalid JSON, remove and return null
      localStorage.removeItem(fullKey);
      return null;
    }
  }

  public async setToken(key: string, value: string, expires_at?: Date): Promise<void> {
    if (typeof localStorage === 'undefined') {
      throw new Error('LocalStorage is not available in this environment');
    }

    const fullKey = this.prefix + key;
    const data = { value, expires_at: expires_at?.toISOString() };
    localStorage.setItem(fullKey, JSON.stringify(data));
  }

  public async removeToken(key: string): Promise<void> {
    if (typeof localStorage === 'undefined') {
      throw new Error('LocalStorage is not available in this environment');
    }

    localStorage.removeItem(this.prefix + key);
  }

  public async clear(): Promise<void> {
    if (typeof localStorage === 'undefined') {
      throw new Error('LocalStorage is not available in this environment');
    }

    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (key.startsWith(this.prefix)) {
        localStorage.removeItem(key);
      }
    }
  }
}

export interface TokenRefreshCallback {
  (refresh_token: string): Promise<TokenResponse>;
}

export class TokenManager {
  private storage: TokenStorage;
  private refresh_callback?: TokenRefreshCallback;
  private refresh_buffer_seconds: number = 300; // 5 minutes
  private refresh_in_progress: boolean = false;

  constructor(
    storage?: TokenStorage,
    refresh_callback?: TokenRefreshCallback,
    refresh_buffer_seconds: number = 300
  ) {
    this.storage = storage || new MemoryTokenStorage();
    this.refresh_callback = refresh_callback;
    this.refresh_buffer_seconds = refresh_buffer_seconds;
  }

  /**
   * Get current access token, refreshing if necessary
   */
  public async getAccessToken(): Promise<string | null> {
    const token = await this.storage.getToken('access_token');
    if (!token) return null;

    // Check if token needs refresh
    if (await this.shouldRefreshToken()) {
      const refreshed = await this.refreshToken();
      return refreshed ? await this.storage.getToken('access_token') : null;
    }

    return token;
  }

  /**
   * Store token response from authentication
   */
  public async storeTokenResponse(token_response: TokenResponse): Promise<void> {
    const expires_at = new Date(Date.now() + (token_response.expires_in * 1000));

    await this.storage.setToken('access_token', token_response.access_token, expires_at);
    await this.storage.setToken('token_type', token_response.token_type);

    if (token_response.refresh_token) {
      await this.storage.setToken('refresh_token', token_response.refresh_token);
    }

    if (token_response.scope) {
      await this.storage.setToken('scope', token_response.scope);
    }

    // Store expiration time for refresh logic
    await this.storage.setToken('expires_at', expires_at.toISOString());
  }

  /**
   * Check if current token needs refreshing
   */
  private async shouldRefreshToken(): Promise<boolean> {
    const expires_at_str = await this.storage.getToken('expires_at');
    if (!expires_at_str) return false;

    const expires_at = new Date(expires_at_str);
    const now = new Date();
    const refresh_at = new Date(expires_at.getTime() - (this.refresh_buffer_seconds * 1000));

    return now >= refresh_at;
  }

  /**
   * Refresh access token using refresh token
   */
  public async refreshToken(): Promise<boolean> {
    if (!this.refresh_callback) {
      throw new AuthenticationError('No refresh callback configured');
    }

    if (this.refresh_in_progress) {
      // Wait for existing refresh to complete
      while (this.refresh_in_progress) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return true;
    }

    this.refresh_in_progress = true;

    try {
      const refresh_token = await this.storage.getToken('refresh_token');
      if (!refresh_token) {
        throw new AuthenticationError('No refresh token available');
      }

      const token_response = await this.refresh_callback(refresh_token);
      await this.storeTokenResponse(token_response);

      return true;
    } catch (error) {
      // Clear tokens on refresh failure
      await this.clearTokens();
      throw error;
    } finally {
      this.refresh_in_progress = false;
    }
  }

  /**
   * Clear all stored tokens
   */
  public async clearTokens(): Promise<void> {
    await this.storage.clear();
  }

  /**
   * Check if user is authenticated
   */
  public async isAuthenticated(): Promise<boolean> {
    try {
      const token = await this.getAccessToken();
      return token !== null;
    } catch {
      return false;
    }
  }

  /**
   * Get authorization header value
   */
  public async getAuthorizationHeader(): Promise<string | null> {
    const token = await this.getAccessToken();
    if (!token) return null;

    const token_type = await this.storage.getToken('token_type') || 'Bearer';
    return `${token_type} ${token}`;
  }
}