/**
 * Utility functions for the Plinto TypeScript SDK
 */

import type { TokenData } from './types';
import { TokenError } from './errors';

/**
 * Base64 URL-safe encoding/decoding utilities
 */
export class Base64Url {
  /**
   * Encode string to base64url
   */
  static encode(str: string): string {
    if (typeof btoa !== 'undefined') {
      // Browser environment
      return btoa(str)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');
    } else {
      // Node.js environment
      return Buffer.from(str, 'utf8')
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');
    }
  }

  /**
   * Decode base64url to string
   */
  static decode(str: string): string {
    // Add padding if needed
    let padded = str;
    while (padded.length % 4) {
      padded += '=';
    }
    
    // Convert base64url to base64
    const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');
    
    if (typeof atob !== 'undefined') {
      // Browser environment
      return atob(base64);
    } else {
      // Node.js environment
      return Buffer.from(base64, 'base64').toString('utf8');
    }
  }
}

/**
 * JWT token utilities
 */
export class JwtUtils {
  /**
   * Decode JWT without verification
   */
  static decode(token: string): any {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new Error('Invalid token format');
      }
      
      const payload = Base64Url.decode(parts[1]);
      return JSON.parse(payload);
    } catch (error) {
      throw new TokenError('Failed to decode token');
    }
  }

  /**
   * Parse JWT token (alias for decode)
   */
  static parseToken(token: string): { header: any; payload: any; signature: string } {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new Error('Invalid token format');
      }
      
      const header = JSON.parse(Base64Url.decode(parts[0]));
      const payload = JSON.parse(Base64Url.decode(parts[1]));
      const signature = parts[2];
      
      return { header, payload, signature };
    } catch (error) {
      throw new TokenError('Failed to parse token');
    }
  }

  /**
   * Get token expiration time
   */
  static getExpiration(token: string): Date | null {
    const payload = JwtUtils.decode(token);
    if (payload.exp) {
      return new Date(payload.exp * 1000);
    }
    return null;
  }

  /**
   * Check if token is expired
   */
  static isExpired(token: string | { exp?: number }): boolean {
    try {
      const payload = typeof token === 'string' ? JwtUtils.decode(token) : token;
      if (!payload.exp) {
        return false; // No expiration means never expires
      }
      
      return Date.now() >= payload.exp * 1000;
    } catch {
      return true; // If we can't decode, consider it expired
    }
  }

  /**
   * Get time until token expiration in seconds
   */
  static getTimeUntilExpiration(token: string): number {
    const expiration = JwtUtils.getExpiration(token);
    return expiration ? Math.max(0, expiration.getTime() - Date.now()) / 1000 : Infinity;
  }

  /**
   * Get time to expiry (alias for getTimeUntilExpiration)
   */
  static getTimeToExpiry(payload: { exp?: number }): number {
    if (!payload.exp) {
      return Infinity;
    }
    return Math.max(0, payload.exp - Math.floor(Date.now() / 1000));
  }

  /**
   * Get user ID from token
   */
  static getUserId(token: string): string | null {
    const payload = JwtUtils.decode(token);
    return payload.sub || payload.user_id || null;
  }

  /**
   * Get JWT ID
   */
  static getJti(token: string): string | null {
    const payload = JwtUtils.decode(token);
    return payload.jti || null;
  }
}

/**
 * Token storage interface and implementations
 */
export interface TokenStorage {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
}

/**
 * Browser localStorage implementation
 */
export class LocalTokenStorage implements TokenStorage {
  async getItem(key: string): Promise<string | null> {
    try {
      if (typeof localStorage !== 'undefined') {
        return localStorage.getItem(key);
      }
    } catch {
      // Silently handle errors
    }
    return null;
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(key, value);
      }
    } catch {
      // Silently handle errors (e.g., quota exceeded)
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(key);
      }
    } catch {
      // Silently handle errors
    }
  }
}

/**
 * Browser sessionStorage implementation
 */
export class SessionTokenStorage implements TokenStorage {
  getItem(key: string): string | null {
    if (typeof sessionStorage === 'undefined') {
      return null;
    }
    return sessionStorage.getItem(key);
  }

  setItem(key: string, value: string): void {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(key, value);
    }
  }

  removeItem(key: string): void {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem(key);
    }
  }
}

/**
 * In-memory token storage (fallback)
 */
export class MemoryTokenStorage implements TokenStorage {
  private storage = new Map<string, string>();

  getItem(key: string): string | null {
    return this.storage.get(key) || null;
  }

  setItem(key: string, value: string): void {
    this.storage.set(key, value);
  }

  removeItem(key: string): void {
    this.storage.delete(key);
  }

  clear(): void {
    this.storage.clear();
  }
}

/**
 * Token manager for handling token storage and retrieval
 */
export class TokenManager {
  private storage: TokenStorage;
  private readonly ACCESS_TOKEN_KEY = 'plinto_access_token';
  private readonly REFRESH_TOKEN_KEY = 'plinto_refresh_token';
  private readonly EXPIRES_AT_KEY = 'plinto_expires_at';

  constructor(storage: TokenStorage) {
    this.storage = storage;
  }

  /**
   * Store tokens
   */
  async setTokens(tokenData: TokenData): Promise<void> {
    await Promise.all([
      this.storage.setItem(this.ACCESS_TOKEN_KEY, tokenData.access_token),
      this.storage.setItem(this.REFRESH_TOKEN_KEY, tokenData.refresh_token),
      this.storage.setItem(this.EXPIRES_AT_KEY, tokenData.expires_at.toString())
    ]);
  }

  /**
   * Get access token
   */
  async getAccessToken(): Promise<string | null> {
    return await this.storage.getItem(this.ACCESS_TOKEN_KEY);
  }

  /**
   * Get refresh token
   */
  async getRefreshToken(): Promise<string | null> {
    return await this.storage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Get token expiration time
   */
  async getExpiresAt(): Promise<number | null> {
    const expiresAt = await this.storage.getItem(this.EXPIRES_AT_KEY);
    return expiresAt ? parseInt(expiresAt, 10) : null;
  }

  /**
   * Get all token data
   */
  async getTokenData(): Promise<TokenData | null> {
    const [accessToken, refreshToken, expiresAt] = await Promise.all([
      this.getAccessToken(),
      this.getRefreshToken(),
      this.getExpiresAt()
    ]);

    if (!accessToken || !refreshToken || !expiresAt) {
      return null;
    }

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_at: expiresAt
    };
  }

  /**
   * Check if tokens are available and valid
   */
  async hasValidTokens(): Promise<boolean> {
    const tokenData = await this.getTokenData();
    if (!tokenData) {
      return false;
    }

    // Check if the expires_at timestamp has passed
    if (tokenData.expires_at && tokenData.expires_at < Date.now()) {
      return false;
    }

    // Also check if the JWT itself is expired
    return !JwtUtils.isExpired(tokenData.access_token);
  }

  /**
   * Clear all tokens
   */
  async clearTokens(): Promise<void> {
    await Promise.all([
      this.storage.removeItem(this.ACCESS_TOKEN_KEY),
      this.storage.removeItem(this.REFRESH_TOKEN_KEY),
      this.storage.removeItem(this.EXPIRES_AT_KEY)
    ]);
  }
}
/**
 * Date utility functions
 */
export class DateUtils {
  /**
   * Check if a timestamp is expired
   */
  static isExpired(timestamp: number): boolean {
    return Date.now() > timestamp;
  }

  /**
   * Format date to ISO string
   */
  static formatISO(date: Date): string {
    return date.toISOString();
  }

  /**
   * Parse ISO string to date
   */
  static parseISO(isoString: string): Date {
    return new Date(isoString);
  }
}

/**
 * URL utility functions
 */
export class UrlUtils {
  /**
   * Parse query string to object
   */
  static parseQueryString(queryString: string): Record<string, string> {
    if (!queryString) return {};
    
    return queryString
      .replace(/^\?/, '')
      .split('&')
      .reduce((acc, pair) => {
        const [key, value] = pair.split('=');
        if (key) {
          acc[decodeURIComponent(key)] = decodeURIComponent(value || '');
        }
        return acc;
      }, {} as Record<string, string>);
  }

  /**
   * Build query string from object
   */
  static buildQueryString(params: Record<string, any>): string {
    const searchParams = new URLSearchParams();
    
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    
    return searchParams.toString();
  }

  /**
   * Build URL with path and optional query parameters
   */
  static buildUrl(baseUrl: string, path?: string, params?: Record<string, any>): string {
    // Remove trailing slash from baseUrl
    const cleanBase = baseUrl.replace(/\/$/, '');
    
    // Remove leading slash from path and handle empty path
    const cleanPath = path ? path.replace(/^\//, '') : '';
    
    // Build the URL
    let url = cleanPath ? `${cleanBase}/${cleanPath}` : cleanBase;
    
    // Add query parameters if provided
    if (params && Object.keys(params).length > 0) {
      const queryString = this.buildQueryString(params);
      url = `${url}?${queryString}`;
    }
    
    return url;
  }
}

/**
 * Validation utility functions
 */
export class ValidationUtils {
  /**
   * Validate email address
   */
  static isValidEmail(email: string): boolean {
    // More strict email regex that doesn't allow consecutive dots
    const emailRegex = /^[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
    
    // Additional check for consecutive dots
    if (email.includes('..')) {
      return false;
    }
    
    return emailRegex.test(email);
  }

  /**
   * Validate password strength
   */
  static isValidPassword(password: string): boolean {
    // At least 8 characters, one uppercase, one lowercase, one number
    // Allow special characters
    const hasMinLength = password.length >= 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumber = /\d/.test(password);
    
    return hasMinLength && hasUpperCase && hasLowerCase && hasNumber;
  }

  /**
   * Validate UUID
   */
  static isValidUuid(uuid: string): boolean {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
  }

  /**
   * Validate URL
   */
  static isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Validate slug format
   */
  static isValidSlug(slug: string): boolean {
    // Slug should only contain lowercase letters, numbers, and hyphens
    // Should not start or end with a hyphen
    const slugRegex = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
    return slugRegex.test(slug);
  }

  static validatePassword(password: string): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (password.length < 8) {
      errors.push('Password must be at least 8 characters long');
    }
    if (!/[A-Z]/.test(password)) {
      errors.push('Password must contain at least one uppercase letter');
    }
    if (!/[a-z]/.test(password)) {
      errors.push('Password must contain at least one lowercase letter');
    }
    if (!/[0-9]/.test(password)) {
      errors.push('Password must contain at least one number');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }

  static isValidUsername(username: string): boolean {
    // Username should be 3-30 characters, alphanumeric with underscores
    const usernameRegex = /^[a-zA-Z0-9_]{3,30}$/;
    return usernameRegex.test(username);
  }
}

export class EnvUtils {
  /**
   * Check if running in browser environment
   */
  static isBrowser(): boolean {
    // Check for real browser, not jsdom
    return typeof window !== 'undefined' && 
           typeof document !== 'undefined' &&
           !!(window as any).navigator &&
           !(window as any).navigator.userAgent?.includes('jsdom');
  }

  /**
   * Check if running in Node.js environment
   */
  static isNode(): boolean {
    return typeof process !== 'undefined' && process.versions && typeof process.versions.node === 'string';
  }

  /**
   * Check if running in web worker
   */
  static isWebWorker(): boolean {
    return typeof WorkerGlobalScope !== 'undefined' && typeof self !== 'undefined';
  }

  /**
   * Get appropriate storage implementation
   */
  static getDefaultStorage(): TokenStorage {
    if (this.isBrowser()) {
      // Try localStorage first, fallback to sessionStorage, then memory
      try {
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('test', 'test');
          localStorage.removeItem('test');
          return new LocalTokenStorage();
        }
      } catch {
        // localStorage might be disabled
      }
      
      try {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem('test', 'test');
          sessionStorage.removeItem('test');
          return new SessionTokenStorage();
        }
      } catch {
        // sessionStorage might be disabled
      }
    }
    
    // Fallback to memory storage
    return new MemoryTokenStorage();
  }
}

/**
 * Retry utilities
 */
export class RetryUtils {
  /**
   * Execute function with exponential backoff retry
   */
  static async withRetry<T>(
    fn: () => Promise<T>,
    maxAttempts = 3,
    baseDelay = 1000,
    backoffFactor = 2,
    maxDelay = 30000
  ): Promise<T> {
    let lastError: any;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        if (attempt === maxAttempts) {
          throw error;
        }
        
        const delay = Math.min(baseDelay * Math.pow(backoffFactor, attempt - 1), maxDelay);
        const jitter = Math.random() * 0.1 * delay;
        
        await this.sleep(delay + jitter);
      }
    }
    
    throw lastError;
  }

  /**
   * Sleep for specified milliseconds
   */
  static sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Event emitter for SDK events
 */
export class EventEmitter<T extends Record<string, any> = Record<string, any>> {
  private listeners = new Map<keyof T, Set<(data: any) => void>>();

  /**
   * Add event listener
   */
  on<K extends keyof T>(event: K, listener: (data: T[K]) => void): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    
    const eventListeners = this.listeners.get(event)!;
    eventListeners.add(listener);
    
    // Return unsubscribe function
    return () => {
      eventListeners.delete(listener);
      if (eventListeners.size === 0) {
        this.listeners.delete(event);
      }
    };
  }

  /**
   * Add one-time event listener
   */
  once<K extends keyof T>(event: K, listener: (data: T[K]) => void): () => void {
    const unsubscribe = this.on(event, (data) => {
      unsubscribe();
      listener(data);
    });
    
    return unsubscribe;
  }

  /**
   * Emit event
   */
  emit<K extends keyof T>(event: K, data: T[K]): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      eventListeners.forEach(listener => {
        try {
          listener(data);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  /**
   * Remove all listeners for an event
   */
  removeAllListeners<K extends keyof T>(event?: K): void {
    if (event) {
      this.listeners.delete(event);
    } else {
      this.listeners.clear();
    }
  }

  /**
   * Get listener count for an event
   */
  listenerCount<K extends keyof T>(event: K): number {
    const eventListeners = this.listeners.get(event);
    return eventListeners ? eventListeners.size : 0;
  }
}