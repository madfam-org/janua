/**
 * Browser behaviour of the background token refresh (jsdom): unchanged by the
 * server-side leak fix, and now stoppable with `destroy()` / `stopAutoRefresh()`.
 */
import { JanuaClient } from '../client';
import { AxiosHttpClient, HttpClient } from '../http-client';
import { AUTO_REFRESH_INTERVAL_MS, AutoRefreshTimer, hasBrowserWindow } from '../auto-refresh';
import { MemoryTokenStorage, TokenManager } from '../utils/token-utils';

const BASE_URL = 'https://auth.example.test';

function browserClient(config: Record<string, unknown> = {}): JanuaClient {
  return new JanuaClient({ baseURL: BASE_URL, tokenStorage: 'memory', ...config });
}

async function seedTokens(client: JanuaClient, expiresInMs: number): Promise<void> {
  const tokens = (client as unknown as { tokenManager: TokenManager }).tokenManager;
  await tokens.setTokens({ access_token: 'a', refresh_token: 'r', expires_at: Date.now() + expiresInMs });
}

/** Let the async refresh check settle under fake timers. */
async function flush(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

describe('JanuaClient auto-refresh in a browser', () => {
  let setIntervalSpy: jest.SpyInstance;
  let clearIntervalSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.useFakeTimers();
    setIntervalSpy = jest.spyOn(global, 'setInterval');
    clearIntervalSpy = jest.spyOn(global, 'clearInterval');
  });

  afterEach(() => {
    setIntervalSpy.mockRestore();
    clearIntervalSpy.mockRestore();
    jest.useRealTimers();
  });

  it('runs with a window (precondition)', () => {
    expect(hasBrowserWindow()).toBe(true);
    expect(new TokenManager(new MemoryTokenStorage())).toBeDefined();
  });

  it('starts one 60 s interval from the constructor by default', () => {
    const client = browserClient();

    expect(client.isAutoRefreshActive()).toBe(true);
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), AUTO_REFRESH_INTERVAL_MS);
    client.destroy();
  });

  it('refreshes a token that expires within five minutes', async () => {
    const client = browserClient();
    await seedTokens(client, 4 * 60 * 1000);
    const refresh = jest.spyOn(client.auth, 'refreshToken').mockResolvedValue({} as never);

    jest.advanceTimersByTime(AUTO_REFRESH_INTERVAL_MS);
    await flush();

    expect(refresh).toHaveBeenCalledTimes(1);
    client.destroy();
  });

  it('leaves a token with plenty of life alone', async () => {
    const client = browserClient();
    await seedTokens(client, 60 * 60 * 1000);
    const refresh = jest.spyOn(client.auth, 'refreshToken').mockResolvedValue({} as never);

    jest.advanceTimersByTime(AUTO_REFRESH_INTERVAL_MS);
    await flush();

    expect(refresh).not.toHaveBeenCalled();
    client.destroy();
  });

  it('emits error (and keeps running) when the refresh fails', async () => {
    const client = browserClient();
    await seedTokens(client, 2 * 60 * 1000);
    const failure = new Error('refresh failed');
    jest.spyOn(client.auth, 'refreshToken').mockRejectedValue(failure);
    const onError = jest.fn();
    client.on('error', onError);

    jest.advanceTimersByTime(AUTO_REFRESH_INTERVAL_MS);
    await flush();

    expect(onError).toHaveBeenCalledWith({ error: failure });
    expect(client.isAutoRefreshActive()).toBe(true);
    client.destroy();
  });

  it('destroy() clears the interval, and no refresh fires afterwards', async () => {
    const client = browserClient();
    await seedTokens(client, 60 * 1000);
    const refresh = jest.spyOn(client.auth, 'refreshToken').mockResolvedValue({} as never);
    const handle = setIntervalSpy.mock.results[0].value;

    client.destroy();
    jest.advanceTimersByTime(AUTO_REFRESH_INTERVAL_MS * 3);
    await flush();

    expect(clearIntervalSpy).toHaveBeenCalledWith(handle);
    expect(client.isAutoRefreshActive()).toBe(false);
    expect(refresh).not.toHaveBeenCalled();
    expect(jest.getTimerCount()).toBe(0);
  });

  it('stop/start is idempotent and resumable (React Strict Mode remount)', () => {
    const client = browserClient();

    expect(client.startAutoRefresh()).toBe(true);
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);

    client.stopAutoRefresh();
    client.stopAutoRefresh();
    expect(client.isAutoRefreshActive()).toBe(false);

    expect(client.startAutoRefresh()).toBe(true);
    expect(setIntervalSpy).toHaveBeenCalledTimes(2);
    expect(client.isAutoRefreshActive()).toBe(true);
    client.destroy();
  });

  it('autoRefreshTokens: false never starts, even when asked', () => {
    const client = browserClient({ autoRefreshTokens: false });

    expect(client.isAutoRefreshActive()).toBe(false);
    expect(client.startAutoRefresh()).toBe(false);
    expect(setIntervalSpy).not.toHaveBeenCalled();
    client.destroy();
  });

  it('destroy() also stops the proactive refresh timer (fetch client)', () => {
    const client = browserClient({ environment: 'browser' });
    const http = (client as unknown as { _httpClient: HttpClient })._httpClient;
    expect(http).toBeInstanceOf(HttpClient);
    const stop = jest.spyOn(http, 'stopProactiveRefresh');

    client.destroy();

    expect(stop).toHaveBeenCalled();
  });

  it('destroy() works with the axios client, which has no proactive timer', () => {
    const client = browserClient();
    const http = (client as unknown as { _httpClient: unknown })._httpClient;
    expect(http).toBeInstanceOf(AxiosHttpClient);

    expect(() => client.destroy()).not.toThrow();
    expect(client.isAutoRefreshActive()).toBe(false);
  });
});

describe('AutoRefreshTimer in a browser', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('ticks on its interval until stopped', () => {
    const tick = jest.fn();
    const timer = new AutoRefreshTimer(tick, 1_000);

    expect(timer.start()).toBe(true);
    expect(timer.start()).toBe(true);
    jest.advanceTimersByTime(3_000);
    expect(tick).toHaveBeenCalledTimes(3);

    timer.stop();
    jest.advanceTimersByTime(3_000);
    expect(tick).toHaveBeenCalledTimes(3);
    expect(timer.active).toBe(false);
  });
});
