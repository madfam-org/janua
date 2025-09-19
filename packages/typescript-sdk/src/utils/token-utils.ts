/**
 * Token-related utilities for JWT handling and token storage
 */

import { TokenError } from '../errors';

/**
 * Base64URL encoding/decoding utilities
 */
export class Base64Url {
  static encode(data: string): string {
    return Buffer.from(data)
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }

  static decode(data: string): string {
    // Add padding if needed
    let base64 = data.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    return Buffer.from(base64, 'base64').toString('utf-8');
  }
}

/**
 * JWT parsing and validation utilities
 */
export class JwtUtils {
  static parseToken(token: string): { header: any; payload: any; signature: string } {
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new TokenError('Invalid JWT format');
    }

    try {
      const header = JSON.parse(Base64Url.decode(parts[0]));
      const payload = JSON.parse(Base64Url.decode(parts[1]));
      const signature = parts[2];
      
      return { header, payload, signature };
    } catch (error) {
      throw new TokenError('Failed to parse JWT payload');
    }
  }

  static isExpired(payload: any): boolean {
    if (!payload || !payload.exp) {
      return false; // No expiration claim
    }
    return Date.now() >= payload.exp * 1000;
  }

  static getTimeToExpiry(payload: any): number {
    if (!payload || !payload.exp) {
      return Infinity; // No expiration
    }
    const expiryMs = payload.exp * 1000;
    const now = Date.now();
    return Math.max(0, Math.floor((expiryMs - now) / 1000));
  }
}

/**
 * Interface for token storage implementations
 */
export interface TokenStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

/**
 * LocalStorage implementation for browser environments
 */
export class LocalTokenStorage implements TokenStorage {
  async getItem(key: string): Promise<string | null> {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      // Silently handle localStorage errors in production
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      // Silently handle localStorage errors in production
    }
  }
}

/**
 * SessionStorage implementation for browser environments
 */
export class SessionTokenStorage implements TokenStorage {
  async getItem(key: string): Promise<string | null> {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null;
    }
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      sessionStorage.setItem(key, value);
    } catch (error) {
      // Silently handle sessionStorage errors in production
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      sessionStorage.removeItem(key);
    } catch (error) {
      // Silently handle sessionStorage errors in production
    }
  }
}

/**
 * In-memory storage implementation
 */
export class MemoryTokenStorage implements TokenStorage {
  private storage = new Map<string, string>();

  async getItem(key: string): Promise<string | null> {
    return this.storage.get(key) || null;
  }

  async setItem(key: string, value: string): Promise<void> {
    this.storage.set(key, value);
  }

  async removeItem(key: string): Promise<void> {
    this.storage.delete(key);
  }
}

/**
 * Token management with storage abstraction
 */
export class TokenManager {
  private readonly ACCESS_TOKEN_KEY = 'plinto_access_token';
  private readonly REFRESH_TOKEN_KEY = 'plinto_refresh_token';
  private readonly EXPIRES_AT_KEY = 'plinto_token_expires_at';

  constructor(private storage: TokenStorage) {}

  async setTokens(tokenData: {
    access_token: string;
    refresh_token: string;
    expires_at: number;
  }): Promise<void> {
    await Promise.all([
      this.storage.setItem(this.ACCESS_TOKEN_KEY, tokenData.access_token),
      this.storage.setItem(this.REFRESH_TOKEN_KEY, tokenData.refresh_token),
      this.storage.setItem(this.EXPIRES_AT_KEY, tokenData.expires_at.toString())
    ]);
  }

  async getAccessToken(): Promise<string | null> {
    return this.storage.getItem(this.ACCESS_TOKEN_KEY);
  }

  async getRefreshToken(): Promise<string | null> {
    return this.storage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Get all tokens
   */
  async getTokens(): Promise<{
    access_token?: string;
    refresh_token?: string;
    expires_at?: number;
  } | null> {
    const [accessToken, refreshToken, expiresAt] = await Promise.all([
      this.getAccessToken(),
      this.getRefreshToken(),
      this.storage.getItem(this.EXPIRES_AT_KEY)
    ]);

    if (!accessToken) {
      return null;
    }

    return {
      access_token: accessToken,
      refresh_token: refreshToken || undefined,
      expires_at: expiresAt ? parseInt(expiresAt, 10) : undefined
    };
  }

  async clearTokens(): Promise<void> {
    await Promise.all([
      this.storage.removeItem(this.ACCESS_TOKEN_KEY),
      this.storage.removeItem(this.REFRESH_TOKEN_KEY),
      this.storage.removeItem(this.EXPIRES_AT_KEY)
    ]);
  }

  /**
   * Synchronous method to get tokens (for backward compatibility)
   * Note: Only works with synchronous storage implementations
   */
  getTokensSync(): { access_token?: string; refresh_token?: string } | null {
    // This is a simplified sync version for LocalStorage/SessionStorage
    // Returns null for async storages
    if (this.storage instanceof LocalTokenStorage || this.storage instanceof SessionTokenStorage) {
      const accessToken = (this.storage as any).storage.getItem(this.ACCESS_TOKEN_KEY);
      const refreshToken = (this.storage as any).storage.getItem(this.REFRESH_TOKEN_KEY);
      
      if (!accessToken) {
        return null;
      }
      
      return {
        access_token: accessToken,
        refresh_token: refreshToken || undefined
      };
    }
    
    // For MemoryTokenStorage
    if (this.storage instanceof MemoryTokenStorage) {
      const accessToken = (this.storage as any).storage.get(this.ACCESS_TOKEN_KEY);
      const refreshToken = (this.storage as any).storage.get(this.REFRESH_TOKEN_KEY);
      
      if (!accessToken) {
        return null;
      }
      
      return {
        access_token: accessToken,
        refresh_token: refreshToken || undefined
      };
    }
    
    return null;
  }

  async hasValidTokens(): Promise<boolean> {
    const [accessToken, expiresAt] = await Promise.all([
      this.getAccessToken(),
      this.storage.getItem(this.EXPIRES_AT_KEY)
    ]);

    if (!accessToken || !expiresAt) {
      return false;
    }

    const expiryTime = parseInt(expiresAt, 10);
    return Date.now() < expiryTime;
  }

  async getTokenData(): Promise<{
    access_token: string;
    refresh_token: string;
    expires_at: number;
  } | null> {
    const [accessToken, refreshToken, expiresAt] = await Promise.all([
      this.getAccessToken(),
      this.getRefreshToken(),
      this.storage.getItem(this.EXPIRES_AT_KEY)
    ]);

    if (!accessToken || !refreshToken || !expiresAt) {
      return null;
    }

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_at: parseInt(expiresAt, 10)
    };
  }
}