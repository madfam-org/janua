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
   * Decode JWT token without verification
   */
  static decode(token: string): any {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new TokenError('Invalid JWT format');
      }

      const payload = Base64Url.decode(parts[1]);
      return JSON.parse(payload);
    } catch (error) {
      throw new TokenError('Failed to decode JWT token', { originalError: error });
    }
  }

  /**
   * Get token expiration time
   */
  static getExpiration(token: string): number {
    const payload = this.decode(token);
    if (!payload.exp) {
      throw new TokenError('Token does not have expiration time');
    }
    return payload.exp * 1000; // Convert to milliseconds
  }

  /**
   * Check if token is expired
   */
  static isExpired(token: string, bufferSeconds = 30): boolean {
    try {
      const expiration = this.getExpiration(token);
      const now = Date.now();
      const buffer = bufferSeconds * 1000;
      return expiration <= (now + buffer);
    } catch {
      return true; // Treat invalid tokens as expired
    }
  }

  /**
   * Get time until token expires (in milliseconds)
   */
  static getTimeUntilExpiration(token: string): number {
    const expiration = this.getExpiration(token);
    return Math.max(0, expiration - Date.now());
  }

  /**
   * Extract user ID from token
   */
  static getUserId(token: string): string {
    const payload = this.decode(token);
    if (!payload.sub) {
      throw new TokenError('Token does not contain user ID');
    }
    return payload.sub;
  }

  /**
   * Extract JTI (JWT ID) from token
   */
  static getJti(token: string): string {
    const payload = this.decode(token);
    if (!payload.jti) {
      throw new TokenError('Token does not contain JTI');
    }
    return payload.jti;
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
  getItem(key: string): string | null {
    if (typeof localStorage === 'undefined') {
      return null;
    }
    return localStorage.getItem(key);
  }

  setItem(key: string, value: string): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value);
    }
  }

  removeItem(key: string): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(key);
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
 * Date and time utilities
 */
export class DateUtils {
  /**
   * Convert ISO date string to Date object
   */
  static fromISOString(isoString: string): Date {
    return new Date(isoString);
  }

  /**
   * Convert Date object to ISO string
   */
  static toISOString(date: Date): string {
    return date.toISOString();
  }

  /**
   * Get current timestamp in milliseconds
   */
  static now(): number {
    return Date.now();
  }

  /**
   * Check if date is in the past
   */
  static isPast(date: Date | string): boolean {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.getTime() < Date.now();
  }

  /**
   * Check if date is in the future
   */
  static isFuture(date: Date | string): boolean {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.getTime() > Date.now();
  }

  /**
   * Format date for display
   */
  static formatRelative(date: Date | string): string {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const now = new Date();
    const diffMs = now.getTime() - dateObj.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return 'just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
    
    return dateObj.toLocaleDateString();
  }
}

/**
 * URL and query parameter utilities
 */
export class UrlUtils {
  /**
   * Build URL with query parameters
   */
  static buildUrl(baseUrl: string, path: string, params?: Record<string, any>): string {
    const url = new URL(path, baseUrl);
    
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
   * Parse query parameters from URL
   */
  static parseQueryParams(url: string): Record<string, string> {
    const urlObj = new URL(url);
    const params: Record<string, string> = {};
    
    urlObj.searchParams.forEach((value, key) => {
      params[key] = value;
    });
    
    return params;
  }

  /**
   * Validate URL format
   */
  static isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Validation utilities
 */
export class ValidationUtils {
  /**
   * Validate email format
   */
  static isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Validate password strength
   */
  static validatePassword(password: string): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (password.length < 8) {
      errors.push('Password must be at least 8 characters long');
    }
    
    if (!/[a-z]/.test(password)) {
      errors.push('Password must contain at least one lowercase letter');
    }
    
    if (!/[A-Z]/.test(password)) {
      errors.push('Password must contain at least one uppercase letter');
    }
    
    if (!/\d/.test(password)) {
      errors.push('Password must contain at least one number');
    }
    
    if (!/[^a-zA-Z0-9]/.test(password)) {
      errors.push('Password must contain at least one special character');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Validate UUID format
   */
  static isValidUUID(uuid: string): boolean {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
  }

  /**
   * Validate username format
   */
  static isValidUsername(username: string): boolean {
    const usernameRegex = /^[a-zA-Z0-9_-]{3,50}$/;
    return usernameRegex.test(username);
  }

  /**
   * Validate organization slug
   */
  static isValidSlug(slug: string): boolean {
    const slugRegex = /^[a-z0-9-]+$/;
    return slugRegex.test(slug) && slug.length >= 1 && slug.length <= 100;
  }
}

/**
 * Webhook signature validation
 */
export class WebhookUtils {
  /**
   * Verify webhook signature
   */
  static async verifySignature(
    payload: string,
    signature: string,
    secret: string
  ): Promise<boolean> {
    try {
      let computedSignature: string;
      
      if (typeof crypto !== 'undefined' && crypto.subtle) {
        // Browser environment with Web Crypto API
        const encoder = new TextEncoder();
        const keyData = encoder.encode(secret);
        const payloadData = encoder.encode(payload);
        
        const cryptoKey = await crypto.subtle.importKey(
          'raw',
          keyData,
          { name: 'HMAC', hash: 'SHA-256' },
          false,
          ['sign']
        );
        
        const signatureBuffer = await crypto.subtle.sign('HMAC', cryptoKey, payloadData);
        const signatureArray = new Uint8Array(signatureBuffer);
        computedSignature = 'sha256=' + Array.from(signatureArray)
          .map(b => b.toString(16).padStart(2, '0'))
          .join('');
      } else {
        // Node.js environment
        const crypto = require('crypto');
        const hmac = crypto.createHmac('sha256', secret);
        hmac.update(payload);
        computedSignature = 'sha256=' + hmac.digest('hex');
      }
      
      return this.safeCompare(signature, computedSignature);
    } catch (error) {
      return false;
    }
  }

  /**
   * Safe string comparison to prevent timing attacks
   */
  private static safeCompare(a: string, b: string): boolean {
    if (a.length !== b.length) {
      return false;
    }
    
    let result = 0;
    for (let i = 0; i < a.length; i++) {
      result |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    
    return result === 0;
  }
}

/**
 * Environment detection utilities
 */
export class EnvUtils {
  /**
   * Check if running in browser environment
   */
  static isBrowser(): boolean {
    return typeof window !== 'undefined' && typeof document !== 'undefined';
  }

  /**
   * Check if running in Node.js environment
   */
  static isNode(): boolean {
    return typeof process !== 'undefined' && process.versions && process.versions.node;
  }

  /**
   * Check if running in web worker
   */
  static isWebWorker(): boolean {
    return typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;
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