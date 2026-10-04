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
/** JWT payload structure */
export interface JwtPayload {
  exp?: number;
  iat?: number;
  sub?: string;
  iss?: string;
  aud?: string | string[];
  [key: string]: unknown;
}

/** JWT header structure */
export interface JwtHeader {
  alg: string;
  typ?: string;
  [key: string]: unknown;
}

export class JwtUtils {
  static parseToken(token: string): { header: JwtHeader; payload: JwtPayload; signature: string } {
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new TokenError('Invalid JWT format');
    }

    try {
      const header = JSON.parse(Base64Url.decode(parts[0] as string)) as JwtHeader;
      const payload = JSON.parse(Base64Url.decode(parts[1] as string)) as JwtPayload;
      const signature = parts[2] as string;

      return { header, payload, signature };
    } catch {
      throw new TokenError('Failed to parse JWT payload');
    }
  }

  static isExpired(payload: JwtPayload | null | undefined): boolean {
    if (!payload || !payload.exp) {
      return false; // No expiration claim
    }
    return Date.now() >= payload.exp * 1000;
  }

  static getTimeToExpiry(payload: JwtPayload | null | undefined): number {
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
      throw new TokenError('Token storage read failed');
    }
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      localStorage.setItem(key, value);
    } catch {
      throw new TokenError('Token storage mutation failed');
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      localStorage.removeItem(key);
    } catch {
      throw new TokenError('Token storage mutation failed');
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
      throw new TokenError('Token storage read failed');
    }
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      sessionStorage.setItem(key, value);
    } catch {
      throw new TokenError('Token storage mutation failed');
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      sessionStorage.removeItem(key);
    } catch {
      throw new TokenError('Token storage mutation failed');
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

export interface SessionSnapshot {
  generation: number;
  sessionId: string | null;
  tokens: { access_token?: string; refresh_token?: string; expires_at?: number } | null;
}
interface StorageScope { generation: number; committedGeneration: number; tail: Promise<void> }
const localScope: StorageScope = { generation: 0, committedGeneration: 0, tail: Promise.resolve() };
const sessionScope: StorageScope = { generation: 0, committedGeneration: 0, tail: Promise.resolve() };
const customScopes = new WeakMap<TokenStorage, StorageScope>();

/**
 * Token management with storage abstraction
 */
export class TokenManager {
  private readonly ACCESS_TOKEN_KEY = 'janua_access_token';
  private readonly REFRESH_TOKEN_KEY = 'janua_refresh_token';
  private readonly EXPIRES_AT_KEY = 'janua_token_expires_at';

  private readonly SESSION_KEY = 'janua_session_generation';
  private readonly STATE_KEY = 'janua_session_state';
  private scope: StorageScope;

  constructor(private storage: TokenStorage) {
    if (storage instanceof LocalTokenStorage) this.scope = localScope;
    else if (storage instanceof SessionTokenStorage) this.scope = sessionScope;
    else {
      let scope = customScopes.get(storage);
      if (!scope) {
        scope = { generation: 0, committedGeneration: 0, tail: Promise.resolve() };
        customScopes.set(storage, scope);
      }
      this.scope = scope;
    }
  }

  get coordinationScope(): object { return this.scope; }
  get sessionGeneration(): number { return this.scope.generation; }

  // Invalidate synchronously, before an async logout/login write can queue.
  invalidateSession(): void { this.scope.generation++; }

  async captureSession(): Promise<SessionSnapshot> {
    const generation = this.scope.generation;
    const sessionId = await this.storage.getItem(this.SESSION_KEY);
    const tokens = await this.getTokens();
    return { generation, sessionId, tokens };
  }

  sameSession(a: SessionSnapshot, b: SessionSnapshot): boolean {
    return a.generation === b.generation && a.sessionId === b.sessionId;
  }

  async sessionMatches(snapshot: SessionSnapshot): Promise<boolean> {
    const current = await this.captureSession();
    return this.sameSession(snapshot, current) &&
      snapshot.tokens?.access_token === current.tokens?.access_token &&
      snapshot.tokens?.refresh_token === current.tokens?.refresh_token;
  }

  // All SDK writers use the same lock as refresh. Web Locks coordinate local
  // storage across tabs. Without them, only this JS realm is coordinated;
  // custom storage implementations need their own cross-process serialization.
  async withSessionLock<T>(work: () => Promise<T>): Promise<T> {
    const previous = this.scope.tail;
    let release!: () => void;
    this.scope.tail = new Promise<void>(resolve => { release = resolve; });
    await previous;
    try {
      if (this.storage instanceof LocalTokenStorage && typeof navigator !== 'undefined' && navigator.locks) {
        return await navigator.locks.request('janua:local-storage:session', work);
      }
      return await work();
    } finally { release(); }
  }

  private async settleMutations(operations: Array<() => Promise<void>>): Promise<void> {
    // A rejected Promise.all returns before other async writes finish. Cleanup
    // must wait for every write, or a late writer could restore cleared tokens.
    const results = await Promise.allSettled(operations.map(operation => Promise.resolve().then(operation)));
    if (results.some(result => result.status === 'rejected')) {
      throw new TokenError('Token storage mutation failed');
    }
  }

  private async writeStorageState(state: 'blocked' | 'valid'): Promise<void> {
    await this.storage.setItem(this.STATE_KEY, state);
    if (await this.storage.getItem(this.STATE_KEY) !== state) {
      throw new TokenError('Token storage state was not persisted');
    }
  }

  private async writeSessionMarker(): Promise<void> {
    const marker = `${Date.now()}:${Math.random()}`;
    await this.storage.setItem(this.SESSION_KEY, marker);
    if (await this.storage.getItem(this.SESSION_KEY) !== marker) {
      throw new TokenError('Token session marker was not persisted');
    }
  }

  private async writeTokens(tokenData: { access_token: string; refresh_token?: string; expires_at: number }): Promise<void> {
    await this.settleMutations([
      () => this.storage.setItem(this.ACCESS_TOKEN_KEY, tokenData.access_token),
      () => tokenData.refresh_token
        ? this.storage.setItem(this.REFRESH_TOKEN_KEY, tokenData.refresh_token)
        : this.storage.removeItem(this.REFRESH_TOKEN_KEY),
      () => this.storage.setItem(this.EXPIRES_AT_KEY, tokenData.expires_at.toString())
    ]);
    const values = await Promise.all([
      this.storage.getItem(this.ACCESS_TOKEN_KEY),
      this.storage.getItem(this.REFRESH_TOKEN_KEY),
      this.storage.getItem(this.EXPIRES_AT_KEY),
    ]);
    if (values[0] !== tokenData.access_token || values[1] !== (tokenData.refresh_token || null) || values[2] !== tokenData.expires_at.toString()) {
      throw new TokenError('Tokens were not persisted');
    }
  }

  // Called only while holding withSessionLock; rotation retains session identity.
  async acceptRefresh(snapshot: SessionSnapshot, tokens: { access_token: string; refresh_token: string; expires_at: number }): Promise<boolean> {
    if (!await this.sessionMatches(snapshot)) return false;
    // Other tabs must not adopt partial writes if persistence or cleanup fails.
    await this.writeStorageState('blocked');
    await this.writeTokens(tokens);
    const sessionId = await this.storage.getItem(this.SESSION_KEY);
    if (!this.sameSession(snapshot, { ...snapshot, generation: this.scope.generation, sessionId })) return false;
    await this.writeStorageState('valid');
    return this.scope.generation === snapshot.generation;
  }

  // A lost refresh response is ambiguous: never reuse that refresh token.
  // Do not clear a logout or another account that superseded this request.
  async discardRefresh(snapshot: SessionSnapshot): Promise<boolean> {
    if (this.scope.generation !== snapshot.generation) return false;
    let sessionId: string | null;
    try {
      sessionId = await this.storage.getItem(this.SESSION_KEY);
    } catch {
      // Cannot prove ownership of persistent data. Hide this realm's tokens,
      // but do not delete a session whose identity we cannot read.
      if (this.scope.generation !== snapshot.generation) return false;
      this.invalidateSession();
      return true;
    }
    if (!this.sameSession(snapshot, { ...snapshot, generation: this.scope.generation, sessionId })) return false;
    // Under the session lock, changed token fields with the SAME identity are
    // our partial rotation. Exact old-token matching would leave them reusable.
    this.invalidateSession();
    const generation = this.scope.generation;
    try {
      await this.removeTokens();
      this.scope.committedGeneration = generation;
    } catch {
      // Removal failed: keep this generation hidden. Never expose a consumed
      // refresh token again or turn cleanup failure into a transport retry.
    }
    return true;
  }

  async setTokens(tokenData: {
    access_token: string;
    refresh_token?: string;
    expires_at: number;
  }): Promise<void> {
    this.invalidateSession();
    const generation = this.scope.generation;
    await this.withSessionLock(async () => {
      await this.writeStorageState('blocked');
      await this.writeSessionMarker();
      await this.writeTokens(tokenData);
      if (this.scope.generation !== generation) return;
      await this.writeStorageState('valid');
      this.scope.committedGeneration = generation;
    });
  }

  async getAccessToken(): Promise<string | null> {
    if (this.scope.generation !== this.scope.committedGeneration) return null;
    if (await this.storage.getItem(this.STATE_KEY) === 'blocked') return null;
    return this.storage.getItem(this.ACCESS_TOKEN_KEY);
  }

  async getRefreshToken(): Promise<string | null> {
    if (this.scope.generation !== this.scope.committedGeneration) return null;
    if (await this.storage.getItem(this.STATE_KEY) === 'blocked') return null;
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

  /** Fence logout at call time, then capture and clear only the owned session.
   * Browser storage reads its marker synchronously before returning its Promise.
   * The Web Lock keeps cross-tab credential capture and removal consistent.
   */
  prepareSignOut(): Promise<{
    accessToken: string | null; refreshToken: string | null;
    generation: number; clearError?: unknown;
  } | null> {
    const identity = this.storage.getItem(this.SESSION_KEY).then(
      value => ({ ok: true as const, value }),
      error => ({ ok: false as const, error }),
    );
    this.invalidateSession();
    const generation = this.scope.generation;
    return this.withSessionLock(async () => {
      const initial = await identity;
      if (!initial.ok) throw initial.error;
      const ownsSession = async () => this.scope.generation === generation &&
        await this.storage.getItem(this.SESSION_KEY) === initial.value &&
        this.scope.generation === generation;
      if (!await ownsSession()) return null;
      const [accessToken, refreshToken] = await Promise.all([
        this.storage.getItem(this.ACCESS_TOKEN_KEY), this.storage.getItem(this.REFRESH_TOKEN_KEY),
      ]);
      if (!await ownsSession()) return null;
      let clearError: unknown;
      try {
        await this.removeTokens();
        this.scope.committedGeneration = generation;
      } catch (error) {
        // Return a settled failure so Auth can attempt server logout with the
        // captured credentials without leaving a rejected clear unobserved.
        clearError = error;
      }
      return { accessToken, refreshToken, generation, clearError };
    });
  }

  async clearTokens(expectedGeneration?: number): Promise<void> {
    if (expectedGeneration !== undefined && this.scope.generation !== expectedGeneration) return;
    this.invalidateSession();
    const generation = this.scope.generation;
    await this.withSessionLock(async () => {
      if (expectedGeneration !== undefined && this.scope.generation !== generation) return;
      await this.removeTokens();
      this.scope.committedGeneration = generation;
    });
  }

  private async removeTokens(): Promise<void> {
    // Attempt all removals even if marker persistence fails, then verify them.
    await this.settleMutations([
      () => this.writeStorageState('blocked'),
      () => this.writeSessionMarker(),
      () => this.storage.removeItem(this.ACCESS_TOKEN_KEY),
      () => this.storage.removeItem(this.REFRESH_TOKEN_KEY),
      () => this.storage.removeItem(this.EXPIRES_AT_KEY)
    ]);
    const remaining = await Promise.all([
      this.storage.getItem(this.ACCESS_TOKEN_KEY),
      this.storage.getItem(this.REFRESH_TOKEN_KEY),
      this.storage.getItem(this.EXPIRES_AT_KEY),
    ]);
    if (remaining.some(value => value !== null)) throw new TokenError('Tokens were not removed');
  }

  /**
   * Synchronous method to get tokens (for backward compatibility)
   * Note: Only works with synchronous storage implementations
   */
  getTokensSync(): { access_token?: string; refresh_token?: string } | null {
    if (this.scope.generation !== this.scope.committedGeneration) return null;
    if (this.storage instanceof LocalTokenStorage || this.storage instanceof SessionTokenStorage) {
      try {
        const storage = this.storage instanceof LocalTokenStorage ? localStorage : sessionStorage;
        if (storage.getItem(this.STATE_KEY) === 'blocked') return null;
        const accessToken = storage.getItem(this.ACCESS_TOKEN_KEY);
        const refreshToken = storage.getItem(this.REFRESH_TOKEN_KEY);
        return accessToken ? { access_token: accessToken, refresh_token: refreshToken || undefined } : null;
      } catch { return null; }
    }

    // For MemoryTokenStorage
    if (this.storage instanceof MemoryTokenStorage) {
      if ((this.storage as any).storage.get(this.STATE_KEY) === 'blocked') return null;
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
