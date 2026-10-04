import React from 'react'
import { act, render, waitFor } from '@testing-library/react'
import { JanuaProvider, useJanua, type JanuaContextValue } from './provider'

jest.mock('@janua/typescript-sdk', () => jest.requireActual('../../typescript-sdk/src'))
jest.mock('./utils/pkce', () => ({
  validateState: () => true,
  retrievePKCEParams: () => ({ verifier: 'fixture-verifier' }),
  clearPKCEParams: jest.fn(),
}))

let context: JanuaContextValue
function Probe() { context = useJanua(); return null }
const originalFetch = global.fetch
const token = `e30.${Buffer.from(JSON.stringify({ sub: 'fixture-subject', exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url')}.fixture`
const tokens = { access_token: token, refresh_token: 'fixture-refresh', expires_in: 3600, token_type: 'bearer' }
const reply = (data: unknown) => ({ ok: true, status: 200, statusText: 'OK', json: async () => data, text: async () => JSON.stringify(data), headers: new Headers({ 'content-type': 'application/json' }) })
beforeEach(() => { jest.useFakeTimers(); localStorage.clear() })
afterEach(() => { context.client.destroy(); jest.clearAllTimers(); jest.useRealTimers(); global.fetch = originalFetch })

it('adopts an OAuth callback after SDK logout through verified token persistence', async () => {
  global.fetch = jest.fn(async (url) => reply(String(url).endsWith('/oauth/token') ? tokens : String(url).endsWith('/auth/me') ? { id: 'fixture-subject', email: 'fixture@example.test' } : {})) as jest.Mock
  render(<JanuaProvider config={{ baseURL: 'https://api.example.test', tokenStorage: 'localStorage', environment: 'browser' as never, autoRefreshTokens: false }}><Probe /></JanuaProvider>)
  await waitFor(() => expect(context.isLoading).toBe(false))
  await act(async () => { await context.signOut() })
  expect(localStorage.getItem('janua_session_state')).toBe('blocked')
  await act(async () => { await context.handleOAuthCallback('fixture-code', 'fixture-state') })
  expect(await context.client.getAccessToken()).toBe(token)
  expect(await context.client.getRefreshToken()).toBe(tokens.refresh_token)
  expect(localStorage.getItem('janua_session_state')).toBe('valid')
  expect(context.isAuthenticated).toBe(true)
})

it('does not import a late OAuth exchange after logout', async () => {
  let finish!: (value: unknown) => void
  global.fetch = jest.fn((url) => String(url).endsWith('/oauth/token') ? new Promise(resolve => { finish = resolve }) : Promise.resolve(reply({}))) as jest.Mock
  render(<JanuaProvider config={{ baseURL: 'https://api.example.test', tokenStorage: 'localStorage', environment: 'browser' as never, autoRefreshTokens: false }}><Probe /></JanuaProvider>)
  await waitFor(() => expect(context.isLoading).toBe(false))
  let callback!: Promise<void>
  act(() => { callback = context.handleOAuthCallback('fixture-code', 'fixture-state') })
  await act(async () => { await context.signOut() })
  await act(async () => { finish(reply(tokens)); await callback })
  expect(await context.client.getAccessToken()).toBeNull()
  expect(context.isAuthenticated).toBe(false)
})
