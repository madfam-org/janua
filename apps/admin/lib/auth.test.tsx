import React from 'react'
import { render, screen, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './auth'

jest.mock('./janua-client', () => {
  const listeners: Record<string, Array<() => void>> = {}
  const client = {
    on: jest.fn((event: string, cb: () => void) => { (listeners[event] = listeners[event] || []).push(cb) }),
    off: jest.fn((event: string, cb: () => void) => { listeners[event] = (listeners[event] || []).filter(fn => fn !== cb) }),
    getAccessToken: jest.fn(),
    getRefreshToken: jest.fn(),
    auth: { signIn: jest.fn(), signOut: jest.fn(), refreshToken: jest.fn() },
    __listeners: listeners,
    __emit: (event: string) => { (listeners[event] || []).forEach(fn => fn()) },
  }
  return { januaClient: client }
})

const { januaClient: client } = jest.requireMock('./janua-client')
const operator = { id: 'operator-id', email: 'operator@janua.dev', is_admin: true }
const mockFetch = jest.fn()
const originalFetch = global.fetch
const originalConsoleError = console.error
let authActions: ReturnType<typeof useAuth>
function Probe() {
  authActions = useAuth()
  const { user, isAuthenticated, isAuthorized, isLoading } = authActions
  return <div>
    <span data-testid="loading">{String(isLoading)}</span>
    <span data-testid="authenticated">{String(isAuthenticated)}</span>
    <span data-testid="authorized">{String(isAuthorized)}</span>
    <span data-testid="email">{user?.email ?? 'none'}</span>
  </div>
}
async function renderProvider() {
  render(<AuthProvider><Probe /></AuthProvider>)
  await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
}
beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation((...args) => {
    // jsdom does not perform full document navigation after logout.
    if (!String(args[0]).includes('Not implemented: navigation')) originalConsoleError(...args)
  })
  jest.clearAllMocks()
  for (const key of Object.keys(client.__listeners)) delete client.__listeners[key]
  client.getAccessToken.mockResolvedValue(null)
  client.getRefreshToken.mockResolvedValue(null)
  localStorage.clear()
  document.cookie = 'janua_access_token=; path=/; max-age=0'
  global.fetch = mockFetch
  mockFetch.mockReset().mockResolvedValue({ ok: true, json: async () => ({ ok: true, user: operator }) })
})
afterEach(() => { jest.restoreAllMocks() })
afterAll(() => { global.fetch = originalFetch })

it('subscribes to canonical SDK events', async () => {
  await renderProvider()
  expect(client.on.mock.calls.map((call: unknown[]) => call[0])).toEqual(['auth:signedIn', 'auth:signedOut', 'token:refreshed'])
})
it('waits for the server bridge before publishing a direct sign-in to route guards', async () => {
  await renderProvider()
  client.getAccessToken.mockResolvedValue('new-token')
  let complete!: (value: unknown) => void
  mockFetch.mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
  await act(async () => { client.__emit('auth:signedIn') })
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  await act(async () => { complete({ ok: true, json: async () => ({ user: operator }) }) })
  await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))
  expect(screen.getByTestId('authorized')).toHaveTextContent('true')
  expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'new-token' }) }))
  expect(document.cookie).not.toContain('janua_admin_')
})
it('hydrates dashboard SSO only through the authoritative bridge', async () => {
  document.cookie = 'janua_access_token=shared-token; path=/'
  await renderProvider()
  expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
  expect(localStorage.getItem('janua_access_token')).toBe('shared-token')
  expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'shared-token' }) }))
})
it.each([401, 403, 503])('does not authenticate when the bridge returns %s', async status => {
  client.getAccessToken.mockResolvedValue('token')
  mockFetch.mockResolvedValue({ ok: false, status })
  await renderProvider()
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  expect(screen.getByTestId('authorized')).toHaveTextContent('false')
})
it('updates the server cookie when the SDK refreshes tokens', async () => {
  client.getAccessToken.mockResolvedValue('old-token')
  await renderProvider()
  client.getAccessToken.mockResolvedValue('refreshed-token')
  await act(async () => { client.__emit('token:refreshed') })
  expect(mockFetch).toHaveBeenLastCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'refreshed-token' }) }))
})
it('does not overwrite a refreshed SDK token while the previous bridge is in flight', async () => {
  await renderProvider()
  client.getAccessToken.mockResolvedValue('old-token')
  let complete!: (value: unknown) => void
  mockFetch.mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
  await act(async () => { client.__emit('auth:signedIn') })
  client.getAccessToken.mockResolvedValue('new-token')
  localStorage.setItem('janua_access_token', 'new-token')
  await act(async () => { client.__emit('token:refreshed') })
  await act(async () => { complete({ ok: true, json: async () => ({ user: operator }) }) })
  await waitFor(() => expect(mockFetch).toHaveBeenLastCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'new-token' }) })))
  expect(localStorage.getItem('janua_access_token')).toBe('new-token')
})
it('refreshes an expired local token once before establishing the session', async () => {
  client.getAccessToken.mockResolvedValueOnce('expired-token').mockResolvedValue('new-token')
  client.getRefreshToken.mockResolvedValue('refresh-token')
  client.auth.refreshToken.mockResolvedValue({})
  mockFetch.mockResolvedValueOnce({ ok: false, status: 401 })
  await renderProvider()
  expect(client.auth.refreshToken).toHaveBeenCalledTimes(1)
  expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
  expect(mockFetch).toHaveBeenLastCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'new-token' }) }))
})
it('recovers a stale admin token using a valid shared dashboard session', async () => {
  client.getAccessToken.mockResolvedValue('stale-token')
  document.cookie = 'janua_access_token=shared-token; path=/'
  mockFetch.mockResolvedValueOnce({ ok: false, status: 401 })
  await renderProvider()
  expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
  expect(mockFetch).toHaveBeenLastCalledWith('/api/auth/session', expect.objectContaining({ body: JSON.stringify({ access_token: 'shared-token' }) }))
})
it('does not resurrect auth state when an in-flight bridge finishes after sign-out', async () => {
  await renderProvider()
  client.getAccessToken.mockResolvedValue('token')
  let complete!: (value: unknown) => void
  mockFetch.mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
  await act(async () => { client.__emit('auth:signedIn') })
  await act(async () => { client.__emit('auth:signedOut') })
  await act(async () => { complete({ ok: true, json: async () => ({ user: operator }) }) })
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
})

it('cancels a queued refresh hydration when sign-out wins, even with a shared SSO cookie', async () => {
  await renderProvider()
  client.getAccessToken.mockResolvedValue('old-token')
  document.cookie = 'janua_access_token=shared-token; path=/'
  let complete!: (value: unknown) => void
  mockFetch.mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
  await act(async () => { client.__emit('auth:signedIn') })
  await act(async () => { client.__emit('token:refreshed') })
  client.getAccessToken.mockResolvedValue(null)
  await act(async () => { client.__emit('auth:signedOut') })
  await act(async () => { complete({ ok: true, json: async () => ({ user: operator }) }) })
  expect(mockFetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
  expect(mockFetch).toHaveBeenLastCalledWith('/api/auth/session', { method: 'DELETE' })
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  expect(localStorage.getItem('janua_access_token')).toBeNull()
})

it('ignores a sign-in response/event that arrives after sign-out', async () => {
  await renderProvider()
  await act(async () => { client.__emit('auth:signedOut') })
  client.getAccessToken.mockResolvedValue('late-signin-token')
  localStorage.setItem('janua_access_token', 'late-signin-token')
  localStorage.setItem('janua_refresh_token', 'late-signin-refresh')
  await act(async () => { client.__emit('auth:signedIn') })
  expect(mockFetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(0)
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  expect(localStorage.getItem('janua_access_token')).toBeNull()
  expect(localStorage.getItem('janua_refresh_token')).toBeNull()
})

it('does not start a bridge when sign-out happens during an async token read', async () => {
  await renderProvider()
  let readToken!: (token: string) => void
  client.getAccessToken.mockReturnValueOnce(new Promise(resolve => { readToken = resolve }))
  await act(async () => { client.__emit('auth:signedIn') })
  await act(async () => { client.__emit('auth:signedOut') })
  await act(async () => { readToken('late-token') })
  expect(mockFetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(0)
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
})


it('rejects a pending login action when sign-out happens before the SDK response', async () => {
  await renderProvider()
  let finishSignIn!: () => void
  client.auth.signIn.mockImplementationOnce(() => new Promise<void>(resolve => {
    finishSignIn = () => { client.__emit('auth:signedIn'); resolve() }
  }))
  let loginResult!: Promise<unknown>
  await act(async () => { loginResult = authActions.login('operator@example.test', 'fixture-password').catch(error => error) })
  await act(async () => { client.__emit('auth:signedOut') })
  client.getAccessToken.mockResolvedValue('late-token')
  await act(async () => { finishSignIn(); await loginResult })
  expect(await loginResult).toBeInstanceOf(Error)
  expect(mockFetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(0)
  expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
})

it('allows a normal login action to reuse its successful event bridge', async () => {
  await renderProvider()
  client.auth.signIn.mockImplementationOnce(async () => {
    client.getAccessToken.mockResolvedValue('new-login-token')
    client.__emit('auth:signedIn')
  })
  await act(async () => { await authActions.login('operator@example.test', 'fixture-password') })
  expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
  expect(mockFetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
})
