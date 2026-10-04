import { Auth } from '../auth';
import { HttpClient, AxiosHttpClient } from '../http-client';
import { MemoryTokenStorage, TokenManager } from '../utils/token-utils';

const old = { access_token: 'fixture-access-old', refresh_token: 'fixture-refresh-old', expires_at: Date.now() + 30_000 };
const rotated = { access_token: 'fixture-access-new', refresh_token: 'fixture-refresh-new', expires_in: 3600, token_type: 'bearer' as const };
const account = { access_token: 'fixture-account-b', refresh_token: 'fixture-account-b-refresh', expires_at: Date.now() + 3600_000 };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
const response = (data: unknown, status = 200) => ({ status, statusText: '', headers: new Headers({ 'Content-Type': 'application/json' }), text: async () => JSON.stringify(data) }) as Response;

type Reply = { status: number; data: unknown };
type Transport = (url: string, data: Record<string, unknown> | undefined, authorization?: string) => Promise<Reply>;
function clientFor(kind: string, manager: TokenManager, transport: Transport) {
  if (kind === 'fetch') {
    jest.mocked(fetch).mockImplementation(async (url, config) => {
      const result = await transport(String(url), config?.body ? JSON.parse(config.body as string) : undefined, (config?.headers as Record<string, string>)?.Authorization);
      return response(result.data, result.status);
    });
    return new HttpClient({ baseURL: 'https://identity.example.test', retryAttempts: 3, retryDelay: 1 }, manager);
  }
  const client = new AxiosHttpClient({ baseURL: 'https://identity.example.test' }, manager);
  // Real Axios interceptors with a fixture adapter; no network or mocked coordinator.
  (client as any).axios.defaults.adapter = async (config: any) => {
    const result = await transport(config.url, config.data ? JSON.parse(config.data) : undefined, config.headers.Authorization);
    const reply = { ...result, statusText: '', headers: {}, config };
    if (result.status >= 400) throw { response: reply, config, message: 'fixture rejection' };
    return reply;
  };
  return client;
}

afterEach(() => { jest.clearAllTimers(); });

describe.each(['fetch', 'axios'])('%s strict refresh rotation', kind => {
  let manager: TokenManager;
  beforeEach(async () => {
    manager = new TokenManager(new MemoryTokenStorage());
    await manager.setTokens(old);
  });

  it('joins direct, proactive and 401 refresh into one token consumption/event', async () => {
    const release = deferred<Reply>();
    const consumed = new Set();
    let refreshes = 0;
    const client = clientFor(kind, manager, async (url, data, bearer) => {
      if (url.endsWith('/auth/refresh')) {
        refreshes++;
        if (consumed.has(data?.refresh_token)) throw new Error('strict one-use token replay');
        consumed.add(data?.refresh_token);
        return release.promise;
      }
      return { status: bearer === `Bearer ${old.access_token}` ? 401 : 200, data: { ok: true } };
    });
    const accepted = jest.fn();
    client.on('token:refreshed', accepted);
    const auth = new Auth(client as HttpClient, manager);
    const direct = auth.refreshToken();
    const concurrent = client.refreshTokens();
    const resource = client.get('/resource');
    if (client instanceof HttpClient) client.startProactiveRefresh();
    await flush();
    expect(refreshes).toBe(1);
    release.resolve({ status: 200, data: rotated });
    await Promise.all([direct, concurrent, resource]);
    expect(refreshes).toBe(1);
    expect(accepted).toHaveBeenCalledTimes(1);
    expect(await manager.getRefreshToken()).toBe(rotated.refresh_token);
    if (client instanceof HttpClient) client.stopProactiveRefresh();
  });

  it('reuses the rotated access token after a delayed old-token 401', async () => {
    const stale = deferred<Reply>();
    let refreshes = 0;
    const client = clientFor(kind, manager, async (url, _data, bearer) => {
      if (url.endsWith('/auth/refresh')) { refreshes++; return { status: 200, data: rotated }; }
      return bearer === `Bearer ${old.access_token}` ? stale.promise : { status: 200, data: { ok: true } };
    });
    const resource = client.get('/resource');
    await flush();
    await client.refreshTokens();
    stale.resolve({ status: 401, data: {} });
    expect((await resource).status).toBe(200);
    expect(refreshes).toBe(1);
    if (client instanceof HttpClient) client.stopProactiveRefresh();
  });

  it.each(['logout', 'account'])('late success cannot replace %s session state', async change => {
    const release = deferred<Reply>();
    const client = clientFor(kind, manager, async () => release.promise);
    const accepted = jest.fn();
    client.on('token:refreshed', accepted);
    const refresh = client.refreshTokens();
    const rejected = expect(refresh).rejects.toThrow('Session changed');
    await flush();
    const mutation = change === 'logout' ? manager.clearTokens() : manager.setTokens(account);
    release.resolve({ status: 200, data: rotated });
    await rejected;
    await mutation;
    expect(await manager.getAccessToken()).toBe(change === 'logout' ? null : account.access_token);
    expect(accepted).not.toHaveBeenCalled();
  });

  it('logout hides credentials immediately and fences a pending refresh', async () => {
    const release = deferred<Reply>();
    const client = clientFor(kind, manager, async url => url.endsWith('/auth/refresh') ? release.promise : { status: 200, data: {} });
    const accepted = jest.fn(), signedOut = jest.fn();
    client.on('token:refreshed', accepted);
    const auth = new Auth(client as HttpClient, manager, undefined, signedOut);
    const refresh = auth.refreshToken();
    const rejected = expect(refresh).rejects.toThrow('Session changed');
    await flush();
    const logout = auth.signOut();
    expect(await manager.getAccessToken()).toBeNull();
    expect(await manager.getRefreshToken()).toBeNull();
    release.resolve({ status: 200, data: rotated });
    await Promise.all([rejected, logout]);
    expect(await manager.getAccessToken()).toBeNull();
    expect(accepted).not.toHaveBeenCalled();
    expect(signedOut).toHaveBeenCalledTimes(1);
  });

  it('late logout completion does not clear or sign out a new account', async () => {
    const release = deferred<Reply>();
    const client = clientFor(kind, manager, async () => release.promise);
    const signedOut = jest.fn();
    const auth = new Auth(client as HttpClient, manager, undefined, signedOut);
    const logout = auth.signOut();
    await flush();
    await manager.setTokens(account);
    release.resolve({ status: 200, data: {} });
    await logout;
    expect(await manager.getAccessToken()).toBe(account.access_token);
    expect(signedOut).not.toHaveBeenCalled();
  });

  it('a late failed refresh cannot clear another account or emit sign-out', async () => {
    const release = deferred<Reply>();
    const client = clientFor(kind, manager, async () => release.promise);
    const signedOut = jest.fn();
    client.on('auth:signedOut', signedOut);
    const refresh = client.refreshTokens();
    const rejected = expect(refresh).rejects.toThrow();
    await flush();
    const mutation = manager.setTokens(account);
    release.reject(new Error('lost response'));
    await rejected;
    await mutation;
    expect(await manager.getAccessToken()).toBe(account.access_token);
    expect(signedOut).not.toHaveBeenCalled();
  });

  it('never retries a consumed refresh token after a lost response', async () => {
    let attempts = 0;
    const client = clientFor(kind, manager, async url => {
      if (url.endsWith('/auth/refresh')) { attempts++; throw new Error('response lost after consume'); }
      return { status: 401, data: {} };
    });
    await expect(client.get('/resource')).rejects.toThrow();
    expect(attempts).toBe(1);
    expect(await manager.getRefreshToken()).toBeNull();
    await expect(client.refreshTokens()).rejects.toThrow('No refresh token');
    expect(attempts).toBe(1);
  });

  it('does not retry a rejected account-A request as account B', async () => {
    const stale = deferred<Reply>();
    let requests = 0;
    const client = clientFor(kind, manager, async () => { requests++; return stale.promise; });
    const resource = client.get('/resource');
    const rejected = expect(resource).rejects.toThrow('Session changed');
    await flush();
    await manager.setTokens(account);
    stale.resolve({ status: 401, data: {} });
    await rejected;
    expect(requests).toBe(1);
    expect(await manager.getAccessToken()).toBe(account.access_token);
  });
});

it('deduplicates different adapters sharing the same storage scope', async () => {
  const storage = new MemoryTokenStorage();
  const a = new TokenManager(storage);
  const b = new TokenManager(storage);
  await a.setTokens(old);
  const release = deferred<Reply>();
  let calls = 0;
  const transport = async () => { calls++; return release.promise; };
  const fetchClient = clientFor('fetch', a, transport);
  const axiosClient = clientFor('axios', b, transport);
  const first = fetchClient.refreshTokens();
  const second = axiosClient.refreshTokens();
  await flush();
  release.resolve({ status: 200, data: rotated });
  await Promise.all([first, second]);
  expect(calls).toBe(1);
  (fetchClient as HttpClient).stopProactiveRefresh();
});

it('uses a Web Lock and storage reread across isolated tab module realms', async () => {
  localStorage.clear();
  let tail = Promise.resolve();
  const request = jest.fn((_name: string, work: () => Promise<unknown>) => {
    const result = tail.then(work);
    tail = result.then(() => undefined, () => undefined);
    return result;
  });
  Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
  const tab = () => {
    let manager: TokenManager;
    let refresh: typeof import('../refresh-coordinator').refreshSession;
    jest.isolateModules(() => {
      const tokens = require('../utils/token-utils');
      manager = new tokens.TokenManager(new tokens.LocalTokenStorage());
      refresh = require('../refresh-coordinator').refreshSession;
    });
    return { manager: manager!, refresh: refresh! };
  };
  try {
    const a = tab(), b = tab();
    await a.manager.setTokens(old);
    const release = deferred<typeof rotated>();
    const transport = jest.fn(() => release.promise);
    const accepted = jest.fn();
    const first = a.refresh(a.manager, transport, accepted, jest.fn());
    const second = b.refresh(b.manager, transport, accepted, jest.fn());
    await flush();
    release.resolve(rotated);
    await Promise.all([first, second]);
    expect(transport).toHaveBeenCalledTimes(1);
    expect(accepted).toHaveBeenCalledTimes(1);
    expect(await b.manager.getRefreshToken()).toBe(rotated.refresh_token);
    expect(request).toHaveBeenCalledWith('janua:local-storage:session', expect.any(Function));
  } finally { Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined }); }
});
