/**
 * @jest-environment node
 *
 * Server-side regression for the per-render interval leak: a JanuaClient
 * built where there is no `window` (Next.js / Nuxt server render, Node
 * scripts) must not leave timers behind. Before the fix every client started
 * a never-cleared 60 s interval, and `<JanuaProvider>` built one per server
 * render, so each page view stayed in memory forever.
 */
import { JanuaClient } from '../client';
import { HttpClient } from '../http-client';
import { AutoRefreshTimer, hasBrowserWindow, unrefTimer } from '../auto-refresh';
import { MemoryTokenStorage, TokenManager } from '../utils/token-utils';

const BASE_URL = 'https://auth.example.test';

/** Live Node `Timeout` handles (setTimeout / setInterval) in this process. */
function activeTimeouts(): number {
  return process.getActiveResourcesInfo().filter((r) => r === 'Timeout').length;
}

describe('JanuaClient without a browser window', () => {
  let setIntervalSpy: jest.SpyInstance;

  beforeEach(() => {
    setIntervalSpy = jest.spyOn(global, 'setInterval');
  });

  afterEach(() => {
    setIntervalSpy.mockRestore();
  });

  it('runs with no window (precondition)', () => {
    expect(typeof window).toBe('undefined');
    expect(hasBrowserWindow()).toBe(false);
  });

  it('constructing N clients starts 0 intervals', () => {
    const before = activeTimeouts();
    const clients = Array.from({ length: 200 }, () => new JanuaClient({ baseURL: BASE_URL }));

    expect(setIntervalSpy).not.toHaveBeenCalled();
    expect(activeTimeouts()).toBe(before);
    for (const client of clients) {
      expect(client.isAutoRefreshActive()).toBe(false);
    }
  });

  it('explicit autoRefreshTokens: true still starts nothing on a server', () => {
    const client = new JanuaClient({ baseURL: BASE_URL, autoRefreshTokens: true });

    expect(client.startAutoRefresh()).toBe(false);
    expect(client.isAutoRefreshActive()).toBe(false);
    expect(setIntervalSpy).not.toHaveBeenCalled();
  });

  it('autoRefreshTokens: false keeps working (the consumer-side guard)', () => {
    const client = new JanuaClient({ baseURL: BASE_URL, autoRefreshTokens: false });

    expect(client.startAutoRefresh()).toBe(false);
    expect(setIntervalSpy).not.toHaveBeenCalled();
  });

  it('destroy() and stopAutoRefresh() are safe and idempotent on a server', () => {
    const client = new JanuaClient({ baseURL: BASE_URL });
    const listener = jest.fn();
    client.on('error', listener);

    expect(() => {
      client.stopAutoRefresh();
      client.destroy();
      client.destroy();
    }).not.toThrow();
    expect(client.listenerCount('error')).toBe(0);
  });

  it('does not auto-connect a configured WebSocket on a server', () => {
    const client = new JanuaClient({ baseURL: BASE_URL, wsUrl: 'wss://ws.example.test' });

    expect(client.ws).toBeDefined();
    expect(client.ws!.getStatus()).toBe('disconnected');
    client.destroy();
  });

  it('wsAutoConnect: true still connects from Node (explicit opt-in)', () => {
    const connect = jest
      .spyOn(jest.requireActual('../websocket').WebSocket.prototype, 'connect')
      .mockResolvedValue(undefined as never);

    const client = new JanuaClient({
      baseURL: BASE_URL,
      wsUrl: 'wss://ws.example.test',
      wsAutoConnect: true,
    });

    expect(connect).toHaveBeenCalledTimes(1);
    client.destroy();
    connect.mockRestore();
  });
});

describe('HttpClient timers without a browser window', () => {
  const storage = () => new TokenManager(new MemoryTokenStorage());

  it('startProactiveRefresh() schedules nothing on a server', async () => {
    const tokens = storage();
    await tokens.setTokens({ access_token: 'a', refresh_token: 'r', expires_at: Date.now() + 3_600_000 });
    const http = new HttpClient({ baseURL: BASE_URL }, tokens);
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

    http.startProactiveRefresh();
    await new Promise((resolve) => setImmediate(resolve));

    expect(setTimeoutSpy).not.toHaveBeenCalled();
    setTimeoutSpy.mockRestore();
  });

  const REQUEST_TIMEOUT_MS = 12_345;

  /** Run `fn`, then return the request-timeout timers it created and whether each was cleared. */
  async function trackRequestTimers(fn: () => Promise<unknown>) {
    const created: unknown[] = [];
    const cleared = new Set<unknown>();
    const realSetTimeout = global.setTimeout;
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout').mockImplementation(((
      cb: () => void,
      ms?: number
    ) => {
      const handle = realSetTimeout(cb, ms);
      if (ms === REQUEST_TIMEOUT_MS) created.push(handle);
      return handle;
    }) as typeof setTimeout);
    const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout').mockImplementation(((handle: never) => {
      cleared.add(handle);
      return (jest.requireActual('timers') as typeof import('timers')).clearTimeout(handle);
    }) as typeof clearTimeout);
    try {
      await fn();
    } finally {
      setTimeoutSpy.mockRestore();
      clearTimeoutSpy.mockRestore();
    }
    return { created, uncleared: created.filter((h) => !cleared.has(h)) };
  }

  it('clears the request timeout once the response has been read', async () => {
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      statusText: 'OK',
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => '{"ok":true}',
    }) as unknown as typeof fetch;
    const http = new HttpClient({ baseURL: BASE_URL, timeout: REQUEST_TIMEOUT_MS }, storage());

    const { created, uncleared } = await trackRequestTimers(() =>
      Promise.all(Array.from({ length: 25 }, () => http.get('/api/v1/health', { skipAuth: true })))
    );

    expect(created).toHaveLength(25);
    expect(uncleared).toHaveLength(0);
    global.fetch = originalFetch;
  });

  it('clears the request timeout when the request fails', async () => {
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockRejectedValue(new TypeError('connection refused')) as unknown as typeof fetch;
    const http = new HttpClient(
      { baseURL: BASE_URL, timeout: REQUEST_TIMEOUT_MS, retryAttempts: 1, retryDelay: 1 },
      storage()
    );

    const { created, uncleared } = await trackRequestTimers(() =>
      expect(http.get('/api/v1/health', { skipAuth: true })).rejects.toThrow()
    );

    expect(created.length).toBeGreaterThan(0);
    expect(uncleared).toHaveLength(0);
    global.fetch = originalFetch;
  });
});

describe('auto-refresh helpers', () => {
  it('AutoRefreshTimer.start() refuses without a window', () => {
    const tick = jest.fn();
    const timer = new AutoRefreshTimer(tick, 10);

    expect(timer.start()).toBe(false);
    expect(timer.active).toBe(false);
    timer.stop();
    expect(tick).not.toHaveBeenCalled();
  });

  it('unrefTimer() unrefs Node timers and ignores numbers and null', () => {
    const timer = setTimeout(() => undefined, 1_000);
    expect(timer.hasRef()).toBe(true);
    unrefTimer(timer);
    expect(timer.hasRef()).toBe(false);
    clearTimeout(timer);

    expect(() => unrefTimer(42)).not.toThrow();
    expect(() => unrefTimer(null)).not.toThrow();
    expect(() => unrefTimer(undefined)).not.toThrow();
  });
});
