import { CookieOptions, RetryOptions } from './types';

// Email validation
export function validateEmail(email: string): boolean {
  if (!email || typeof email !== 'string') return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// Password validation (min 8 chars, uppercase, lowercase, number, special char)
export function validatePassword(password: string): boolean {
  if (!password || typeof password !== 'string') return false;
  if (password.length < 8) return false;
  
  const hasUpperCase = /[A-Z]/.test(password);
  const hasLowerCase = /[a-z]/.test(password);
  const hasNumber = /\d/.test(password);
  const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);
  
  return hasUpperCase && hasLowerCase && hasNumber && hasSpecialChar;
}

// JWT parsing
export function parseJWT(token: string): any | null {
  try {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    
    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

// Token expiration check
export function isTokenExpired(token: any, bufferSeconds: number = 0): boolean {
  if (!token || typeof token.exp !== 'number') return true;
  const now = Math.floor(Date.now() / 1000);
  return token.exp < (now + bufferSeconds);
}

// PKCE code verifier generation
export function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64URLEncode(array);
}

// PKCE code challenge generation
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const hash = await sha256(verifier);
  return base64URLEncode(hash);
}

// Base64 URL encoding
export function base64URLEncode(buffer: Uint8Array): string {
  const base64 = btoa(String.fromCharCode(...buffer));
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

// SHA-256 hashing
export async function sha256(text: string): Promise<Uint8Array> {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(hashBuffer);
}

// Query string builder
export function buildQueryString(params: Record<string, any>): string {
  const parts: string[] = [];
  
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) continue;
    
    if (Array.isArray(value)) {
      for (const item of value) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(item)}`);
      }
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
    }
  }
  
  return parts.join('&');
}

// Query string parser
export function parseQueryString(query: string): Record<string, any> {
  const params: Record<string, any> = {};
  
  if (!query) return params;
  if (query.startsWith('?')) query = query.slice(1);
  
  const parts = query.split('&');
  for (const part of parts) {
    const [key, value] = part.split('=');
    if (!key) continue;
    
    const decodedKey = decodeURIComponent(key);
    const decodedValue = value ? decodeURIComponent(value) : '';
    
    if (params[decodedKey] !== undefined) {
      if (!Array.isArray(params[decodedKey])) {
        params[decodedKey] = [params[decodedKey]];
      }
      params[decodedKey].push(decodedValue);
    } else {
      params[decodedKey] = decodedValue;
    }
  }
  
  return params;
}

// Cookie management
export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [cookieName, cookieValue] = cookie.trim().split('=');
    if (cookieName === name) {
      return decodeURIComponent(cookieValue);
    }
  }
  return null;
}

export function setCookie(name: string, value: string, options: CookieOptions = {}): void {
  if (typeof document === 'undefined') return;
  
  let cookie = `${name}=${encodeURIComponent(value)}`;
  
  if (options.expires) {
    const expires = options.expires instanceof Date 
      ? options.expires 
      : new Date(Date.now() + options.expires);
    cookie += `; expires=${expires.toUTCString()}`;
  }
  
  if (options.path) cookie += `; path=${options.path}`;
  if (options.domain) cookie += `; domain=${options.domain}`;
  if (options.secure) cookie += '; secure';
  if (options.sameSite) cookie += `; samesite=${options.sameSite}`;
  
  document.cookie = cookie;
}

export function deleteCookie(name: string, options: CookieOptions = {}): void {
  setCookie(name, '', { ...options, expires: new Date(0) });
}

// Debounce function
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout;
  
  return function (...args: Parameters<T>) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

// Throttle function
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0;
  
  return function (...args: Parameters<T>) {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      fn(...args);
    }
  };
}

// Retry function
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoff = 1,
    retryCondition = () => true
  } = options;
  
  let lastError: any;
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      if (attempt === maxAttempts - 1 || !retryCondition(error)) {
        throw error;
      }
      
      const waitTime = delay * Math.pow(backoff, attempt);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw lastError;
}

// Error formatting
export function formatError(error: any): string {
  if (error instanceof Error) {
    return error.message;
  }
  
  if (error?.response?.data?.error) {
    return error.response.data.error;
  }
  
  if (error?.message) {
    return error.message;
  }
  
  if (typeof error === 'string') {
    return error;
  }
  
  return 'An unknown error occurred';
}

// Input sanitization
export function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') return '';
  
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;'
  };
  
  return input.replace(/[&<>"'\/]/g, char => map[char]);
}

// Browser fingerprint generation
export function generateFingerprint(): string {
  if (typeof window === 'undefined') return 'server';
  
  const components = [
    navigator.userAgent,
    navigator.language,
    screen.colorDepth,
    screen.width,
    screen.height,
    new Date().getTimezoneOffset(),
    navigator.hardwareConcurrency,
    navigator.platform
  ];
  
  return hashValue(components.join('|'));
}

// Simple hash function
export function hashValue(value: any): string {
  const str = typeof value === 'string' ? value : JSON.stringify(value);
  let hash = 0;
  
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  
  return Math.abs(hash).toString(36);
}

// Local storage wrapper with fallback
export class StorageManager {
  private storage: Storage | null = null;
  private memoryStorage: Map<string, string> = new Map();
  
  constructor(type: 'local' | 'session' = 'local') {
    if (typeof window !== 'undefined') {
      try {
        this.storage = type === 'local' ? localStorage : sessionStorage;
        // Test if storage is available
        const testKey = '__plinto_test__';
        this.storage.setItem(testKey, 'test');
        this.storage.removeItem(testKey);
      } catch {
        this.storage = null;
      }
    }
  }
  
  getItem(key: string): string | null {
    if (this.storage) {
      try {
        return this.storage.getItem(key);
      } catch {
        // Fallback to memory
      }
    }
    return this.memoryStorage.get(key) || null;
  }
  
  setItem(key: string, value: string): void {
    if (this.storage) {
      try {
        this.storage.setItem(key, value);
        return;
      } catch {
        // Fallback to memory
      }
    }
    this.memoryStorage.set(key, value);
  }
  
  removeItem(key: string): void {
    if (this.storage) {
      try {
        this.storage.removeItem(key);
      } catch {
        // Continue to memory removal
      }
    }
    this.memoryStorage.delete(key);
  }
  
  clear(): void {
    if (this.storage) {
      try {
        this.storage.clear();
      } catch {
        // Continue to memory clear
      }
    }
    this.memoryStorage.clear();
  }
}

// Deep clone utility
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj.getTime()) as any;
  if (obj instanceof Array) return obj.map(item => deepClone(item)) as any;
  if (obj instanceof Object) {
    const cloned = {} as any;
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = deepClone(obj[key]);
      }
    }
    return cloned;
  }
  return obj;
}

// URL safe base64 decode
export function base64URLDecode(str: string): string {
  const base64 = str
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(str.length + (4 - str.length % 4) % 4, '=');
  return atob(base64);
}

// Random string generation
export function generateRandomString(length: number = 32): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, byte => chars[byte % chars.length]).join('');
}

// Check if running in browser
export function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

// Check if running in Node.js
export function isNode(): boolean {
  return typeof process !== 'undefined' && process.versions && process.versions.node;
}

// Safe JSON parse
export function safeJSONParse<T = any>(text: string, fallback?: T): T | undefined {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

// Format date for API
export function formatDate(date: Date | string | number): string {
  const d = date instanceof Date ? date : new Date(date);
  return d.toISOString();
}

// Parse API date
export function parseDate(date: string): Date {
  return new Date(date);
}