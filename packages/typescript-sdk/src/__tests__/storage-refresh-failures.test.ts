import { Auth } from '../auth';
import { CoreAuthService } from '../auth/core-auth-service';
import { HttpClient } from '../http-client';
import { refreshSession } from '../refresh-coordinator';
import { LocalTokenStorage, MemoryTokenStorage, SessionTokenStorage, TokenManager } from '../utils/token-utils';

const keys = { access: 'janua_access_token', refresh: 'janua_refresh_token', expires: 'janua_token_expires_at', session: 'janua_session_generation', state: 'janua_session_state' };
const original = { access_token: 'fixture-old-access', refresh_token: 'fixture-old-refresh', expires_at: 1000 };
const rotated = { access_token: 'fixture-new-access', refresh_token: 'fixture-new-refresh', expires_in: 3600, token_type: 'bearer' as const };
const account = { access_token: 'fixture-account-b', refresh_token: 'fixture-account-b-refresh', expires_at: 2000 };
const flush = async () => { for (let i = 0; i < 50; i++) await Promise.resolve(); };

function browserStore() {
  const values = new Map<string, string>();
  const failWrites = new Set<string>(), failRemovals = new Set<string>();
  let drop = false;
  return {
    values, failWrites, failRemovals,
    setDrop(value: boolean) { drop = value; },
    getItem(key: string) { return values.get(key) ?? null; },
    setItem(key: string, value: string) {
      if (failWrites.has(key)) { if (drop) return; throw new Error('fixture storage failure'); }
      values.set(key, value);
    },
    removeItem(key: string) {
      if (failRemovals.has(key)) { if (drop) return; throw new Error('fixture storage failure'); }
      values.delete(key);
    },
  };
}

describe.each(['localStorage', 'sessionStorage'] as const)('%s storage failure safety', name => {
  let previous: PropertyDescriptor | undefined;
  let store: ReturnType<typeof browserStore>;
  let manager: TokenManager;
  const create = () => name === 'localStorage' ? new LocalTokenStorage() : new SessionTokenStorage();
  beforeEach(async () => {
    previous = Object.getOwnPropertyDescriptor(window, name);
    store = browserStore();
    Object.defineProperty(window, name, { configurable: true, value: store });
    manager = new TokenManager(create());
    await manager.setTokens(original);
  });
  afterEach(() => { if (previous) Object.defineProperty(window, name, previous); });

  it.each(['throw', 'drop'])('discards an owned partial rotation after a selective write failure: %s', async mode => {
    store.setDrop(mode === 'drop'); store.failWrites.add(keys.refresh);
    const transport = jest.fn().mockResolvedValue(rotated), accepted = jest.fn(), expired = jest.fn();
    await expect(refreshSession(manager, transport, accepted, expired)).rejects.toThrow();
    expect(transport).toHaveBeenCalledTimes(1);
    expect(accepted).not.toHaveBeenCalled(); expect(expired).toHaveBeenCalledTimes(1);
    expect(await manager.getAccessToken()).toBeNull(); expect(await manager.getRefreshToken()).toBeNull();
    expect(store.values.has(keys.access)).toBe(false); expect(store.values.has(keys.refresh)).toBe(false);
    await expect(refreshSession(manager, transport, accepted, expired)).rejects.toThrow('No refresh token');
    expect(transport).toHaveBeenCalledTimes(1);
  });

  it.each(['throw', 'drop'])('keeps credentials hidden when partial-refresh cleanup fails: %s', async mode => {
    store.setDrop(mode === 'drop'); store.failWrites.add(keys.refresh);
    store.failRemovals.add(keys.access); store.failRemovals.add(keys.refresh);
    const transport = jest.fn().mockResolvedValue(rotated), accepted = jest.fn();
    await expect(refreshSession(manager, transport, accepted, jest.fn())).rejects.toThrow();
    expect(store.values.get(keys.access)).toBe(rotated.access_token);
    expect(store.values.get(keys.refresh)).toBe(original.refresh_token);
    expect(await manager.getAccessToken()).toBeNull(); expect(await manager.getRefreshToken()).toBeNull();
    expect(manager.getTokensSync()).toBeNull();
    expect(await new TokenManager(create()).getRefreshToken()).toBeNull();
    expect(store.values.get(keys.state)).toBe('blocked');
    // A fresh module realm (another tab) has no in-memory invalidation history.
    let other: TokenManager;
    jest.isolateModules(() => {
      const tokens = require('../utils/token-utils');
      other = new tokens.TokenManager(name === 'localStorage' ? new tokens.LocalTokenStorage() : new tokens.SessionTokenStorage());
    });
    expect(await other!.getRefreshToken()).toBeNull();
    expect(other!.getTokensSync()).toBeNull();
    await expect(refreshSession(manager, transport, accepted, jest.fn())).rejects.toThrow('No refresh token');
    expect(transport).toHaveBeenCalledTimes(1); expect(accepted).not.toHaveBeenCalled();
    store.failWrites.clear(); store.failRemovals.clear();
    await manager.setTokens(account);
    expect(await manager.getAccessToken()).toBe(account.access_token);
  });

  it.each(['throw', 'drop'])('failed explicit removal rejects without exposing stale credentials: %s', async mode => {
    store.setDrop(mode === 'drop'); store.failRemovals.add(keys.refresh);
    await expect(manager.clearTokens()).rejects.toThrow();
    expect(store.values.get(keys.refresh)).toBe(original.refresh_token);
    expect(await manager.getRefreshToken()).toBeNull();
    expect(await new TokenManager(create()).getRefreshToken()).toBeNull();
    expect(await manager.hasValidTokens()).toBe(false);
  });

  it.each([keys.session, keys.access, keys.refresh, keys.expires])('failed login persistence never publishes a mixed session: %s', async key => {
    store.setDrop(true); store.failWrites.add(key);
    await expect(manager.setTokens(account)).rejects.toThrow();
    expect(await manager.getAccessToken()).toBeNull(); expect(await manager.getRefreshToken()).toBeNull();
    expect(manager.getTokensSync()).toBeNull();
  });

  it.each([Auth, CoreAuthService])('attaches a failed clear immediately while logout HTTP is pending (%p)', async AuthClass => {
    store.failRemovals.add(keys.refresh);
    let release!: (value: unknown) => void;
    const http = { post: jest.fn(() => new Promise(resolve => { release = resolve; })) } as unknown as HttpClient;
    const auth = new AuthClass(http, manager);
    const logout = auth.signOut();
    const rejected = expect(logout).rejects.toThrow('Token storage mutation failed');
    // Advance a real event-loop turn: an unattached clearing rejection fails Jest.
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(await manager.getRefreshToken()).toBeNull();
    release({ data: {} });
    await rejected;
  });
});

it('waits for every async write before clearing a failed rotation', async () => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  class AsyncStorage extends MemoryTokenStorage {
    fail = false;
    async setItem(key: string, value: string) {
      if (this.fail && key === keys.refresh) throw new Error('fixture rejected write');
      if (this.fail && key === keys.expires) await gate;
      await super.setItem(key, value);
    }
  }
  const storage = new AsyncStorage(), manager = new TokenManager(storage);
  await manager.setTokens(original); storage.fail = true;
  const expired = jest.fn();
  const result = refreshSession(manager, async () => rotated, jest.fn(), expired);
  const rejected = expect(result).rejects.toThrow();
  await flush(); expect(expired).not.toHaveBeenCalled(); release(); await rejected;
  expect(await storage.getItem(keys.access)).toBeNull(); expect(await storage.getItem(keys.refresh)).toBeNull();
  expect(await storage.getItem(keys.expires)).toBeNull();
});

it('partial-write failure cannot clear an account queued during persistence', async () => {
  let switching: Promise<void> | undefined;
  let manager: TokenManager;
  class SwitchingStorage extends MemoryTokenStorage {
    async setItem(key: string, value: string) {
      if (key === keys.access && value === rotated.access_token) switching = manager.setTokens(account);
      if (key === keys.refresh && value === rotated.refresh_token) throw new Error('fixture rejected write');
      await super.setItem(key, value);
    }
  }
  manager = new TokenManager(new SwitchingStorage()); await manager.setTokens(original);
  const expired = jest.fn(), accepted = jest.fn();
  await expect(refreshSession(manager, async () => rotated, accepted, expired)).rejects.toThrow();
  await switching;
  expect(await manager.getAccessToken()).toBe(account.access_token);
  expect(await manager.getRefreshToken()).toBe(account.refresh_token);
  expect(accepted).not.toHaveBeenCalled(); expect(expired).not.toHaveBeenCalled();
});

describe.each([Auth, CoreAuthService])('logout credential-read ownership (%p)', AuthClass => {
  it('does not clear or revoke an account started immediately after logout', async () => {
    const manager = new TokenManager(new MemoryTokenStorage());
    await manager.setTokens(original);
    const post = jest.fn().mockResolvedValue({ data: {} }), signedOut = jest.fn();
    const auth = new AuthClass({ post } as unknown as HttpClient, manager, undefined, signedOut);
    const logout = auth.signOut();
    const login = manager.setTokens(account);
    await Promise.all([logout, login]);
    expect(await manager.getAccessToken()).toBe(account.access_token);
    expect(await manager.getRefreshToken()).toBe(account.refresh_token);
    expect(post).not.toHaveBeenCalled(); expect(signedOut).not.toHaveBeenCalled();
  });

  it('never sends replacement credentials after deferred logout storage reads', async () => {
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    class DeferredStorage extends MemoryTokenStorage {
      defer = false;
      async getItem(key: string) {
        if (this.defer && (key === keys.access || key === keys.refresh)) await gate;
        return super.getItem(key);
      }
    }
    const storage = new DeferredStorage(), manager = new TokenManager(storage);
    await manager.setTokens(original); storage.defer = true;
    const post = jest.fn().mockResolvedValue({ data: {} }), signedOut = jest.fn();
    const auth = new AuthClass({ post } as unknown as HttpClient, manager, undefined, signedOut);
    const logout = auth.signOut();
    await flush();
    const login = manager.setTokens(account);
    await flush(); release();
    await Promise.all([logout, login]);
    expect(await manager.getAccessToken()).toBe(account.access_token);
    expect(post).not.toHaveBeenCalled(); expect(signedOut).not.toHaveBeenCalled();
  });
});

it('an owned clear queued behind the session lock cannot remove a newer account', async () => {
  const manager = new TokenManager(new MemoryTokenStorage());
  await manager.setTokens(original);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const blocker = manager.withSessionLock(() => gate);
  const logout = manager.clearTokens(manager.sessionGeneration);
  const login = manager.setTokens(account);
  release(); await Promise.all([blocker, logout, login]);
  expect(await manager.getAccessToken()).toBe(account.access_token);
});

it('access-only adoption unblocks a trusted session without retaining another account refresh token', async () => {
  const { JanuaClient } = await import('../client');
  const client = new JanuaClient({ baseURL: 'https://api.example.test', tokenStorage: 'memory', autoRefreshTokens: false });
  await client.setTokens(rotated);
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  const token = `e30.${payload}.fixture`;
  await client.adoptAccessToken(token);
  expect(await client.getAccessToken()).toBe(token);
  expect(await client.getRefreshToken()).toBeNull();
  expect(await client.isAuthenticated()).toBe(true);
  client.destroy();
});

it('rejects malformed or expired access-only imports without replacing current credentials', async () => {
  const { JanuaClient } = await import('../client');
  const client = new JanuaClient({ baseURL: 'https://api.example.test', tokenStorage: 'memory', autoRefreshTokens: false });
  await client.setTokens(rotated);
  await expect(client.adoptAccessToken('fixture-invalid')).rejects.toThrow();
  const payload = Buffer.from(JSON.stringify({ exp: 1 })).toString('base64url');
  await expect(client.adoptAccessToken(`e30.${payload}.fixture`)).rejects.toThrow('future expiry');
  expect(await client.getAccessToken()).toBe(rotated.access_token);
  expect(await client.getRefreshToken()).toBe(rotated.refresh_token);
  client.destroy();
});

describe.each([Auth, CoreAuthService])('cross-tab logout ownership (%p)', AuthClass => {
  it('does not clear or send another tab account credentials after waiting for its lock', async () => {
    localStorage.clear();
    let tail = Promise.resolve();
    const request = jest.fn((_name: string, work: () => Promise<unknown>) => {
      const result = tail.then(work);
      tail = result.then(() => undefined, () => undefined);
      return result;
    });
    const previous = Object.getOwnPropertyDescriptor(navigator, 'locks');
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    const tab = () => {
      let manager: TokenManager;
      jest.isolateModules(() => {
        const tokens = require('../utils/token-utils');
        manager = new tokens.TokenManager(new tokens.LocalTokenStorage());
      });
      return manager!;
    };
    try {
      const a = tab(), b = tab();
      await a.setTokens(original);
      let release!: () => void;
      const gate = new Promise<void>(resolve => { release = resolve; });
      const blocker = request('janua:local-storage:session', () => gate);
      const login = b.setTokens(account);
      await flush();
      const post = jest.fn().mockResolvedValue({ data: {} }), signedOut = jest.fn();
      const auth = new AuthClass({ post } as unknown as HttpClient, a, undefined, signedOut);
      const logout = auth.signOut();
      await flush(); release();
      await Promise.all([blocker, login, logout]);
      expect(await b.getAccessToken()).toBe(account.access_token);
      expect(await b.getRefreshToken()).toBe(account.refresh_token);
      expect(post).not.toHaveBeenCalled(); expect(signedOut).not.toHaveBeenCalled();
    } finally {
      if (previous) Object.defineProperty(navigator, 'locks', previous);
      else Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined });
    }
  });
});
