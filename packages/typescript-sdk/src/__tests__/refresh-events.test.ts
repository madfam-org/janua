/** Exercise real client/Auth/HTTP forwarding, rather than manually emitting the event. */
jest.mock('../graphql', () => ({ GraphQL: jest.fn() }));
jest.mock('../websocket', () => ({ WebSocket: jest.fn() }));
import { JanuaClient } from '../client';
// Select the fetch transport while retaining its real refresh/event behavior.
jest.mock('../http-client', () => {
  const actual = jest.requireActual('../http-client');
  return { ...actual, createHttpClient: (config: unknown, tokens: unknown) => new actual.HttpClient(config, tokens) };
});

const rotated = { access_token: 'fixture-access', refresh_token: 'fixture-refresh', expires_in: 3600, token_type: 'bearer' as const };
const response = (body: unknown, status = 200) => ({
  status, statusText: status === 200 ? 'OK' : 'Unauthorized',
  headers: new Headers({ 'Content-Type': 'application/json' }), text: async () => JSON.stringify(body),
}) as Response;

let client: JanuaClient;
let canonical: jest.Mock;
let alias: jest.Mock;
beforeEach(() => {
  jest.useFakeTimers();
  localStorage.clear();
  localStorage.setItem('janua_access_token', 'old-access');
  localStorage.setItem('janua_refresh_token', 'old-refresh');
  localStorage.setItem('janua_token_expires_at', String(Date.now() + 180_000));
  client = new JanuaClient({ baseURL: 'https://identity.example.test', tokenStorage: 'localStorage', autoRefreshTokens: true });
  canonical = jest.fn();
  alias = jest.fn();
  client.on('token:refreshed', canonical);
  client.on('tokenRefreshed' as never, alias);
  jest.mocked(fetch).mockReset().mockResolvedValue(response(rotated));
});
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

it('emits exactly once after a direct refresh has persisted credentials', async () => {
  let storedAtEvent: string | null = null;
  client.on('token:refreshed', () => { storedAtEvent = localStorage.getItem('janua_access_token'); });
  await client.auth.refreshToken();
  expect(canonical).toHaveBeenCalledTimes(1);
  expect(alias).toHaveBeenCalledTimes(1);
  expect(canonical).toHaveBeenCalledWith({ tokens: rotated });
  expect(storedAtEvent).toBe(rotated.access_token);
});

it('emits exactly once from the scheduled refresh path', async () => {
  await jest.advanceTimersByTimeAsync(60_000);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(canonical).toHaveBeenCalledTimes(1);
  expect(alias).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem('janua_refresh_token')).toBe(rotated.refresh_token);
});

it('keeps HTTP 401 recovery at exactly one refresh event', async () => {
  jest.mocked(fetch).mockResolvedValueOnce(response({}, 401))
    .mockResolvedValueOnce(response(rotated)).mockResolvedValueOnce(response({ id: 'fixture-user' }));
  await client.auth.getCurrentUser();
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(canonical).toHaveBeenCalledTimes(1);
  expect(alias).toHaveBeenCalledTimes(1);
});

it('emits no success event for an incomplete token response', async () => {
  jest.mocked(fetch).mockResolvedValue(response({ access_token: 'incomplete' }));
  await client.auth.refreshToken();
  expect(canonical).not.toHaveBeenCalled();
  expect(alias).not.toHaveBeenCalled();
  expect(localStorage.getItem('janua_access_token')).toBe('old-access');
});
