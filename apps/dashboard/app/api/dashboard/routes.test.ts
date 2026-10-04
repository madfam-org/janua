/** @jest-environment node */
import { NextRequest } from 'next/server'
import { GET as getStats } from './stats/route'
import { GET as getActivity } from './recent-activity/route'

const originalFetch = global.fetch
const mockFetch = jest.fn()
const request = (token = 'fixture-token') => new NextRequest('https://app.example/api/dashboard/stats', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
beforeEach(() => {
  global.fetch = mockFetch
  mockFetch.mockReset()
})
afterAll(() => { global.fetch = originalFetch })

it('proxies only account-scoped counts and returns no platform metrics', async () => {
  mockFetch.mockImplementation(async (url: string) => ({ ok: true, json: async () => url.endsWith('/organizations/') ? { organizations: [{ id: 'org-a' }], total: 1, page: 1, per_page: 20 } : { sessions: [], total: 0 } }))
  const response = await getStats(request())
  expect(response.status).toBe(200)
  expect(await response.json()).toEqual({ organizations: 1, activeSessions: 0 })
  expect(mockFetch.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/api/v1/organizations/', '/api/v1/sessions/'])
  for (const [, options] of mockFetch.mock.calls) expect(options).toMatchObject({ headers: { Authorization: 'Bearer fixture-token' }, cache: 'no-store', redirect: 'error' })
  expect(response.headers.get('cache-control')).toBe('no-store')
})
it('requires a bearer token before making upstream requests', async () => {
  expect((await getStats(request(''))).status).toBe(401)
  expect((await getActivity(request(''))).status).toBe(401)
  expect(mockFetch).not.toHaveBeenCalled()
})
it('returns unavailable instead of zeros on malformed responses', async () => {
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ total_users: 999 }) })
  const response = await getStats(request())
  expect(response.status).toBe(503)
  expect(await response.json()).toEqual({ message: 'Account overview unavailable' })
})
it('does not expose upstream identity payloads or errors when auth fails', async () => {
  mockFetch.mockResolvedValue({ ok: false, status: 403, json: async () => ({ private_detail: 'fixture-only' }) })
  const response = await getActivity(request())
  expect(response.status).toBe(403)
  expect(await response.json()).toEqual({ message: 'Your session activity is unavailable' })
})
it('returns only the current-user session fields needed by the overview', async () => {
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ activities: [{ session_id: 'session-a', activity_type: 'session_created', timestamp: null, revoked: false, device: 'Example browser', ip_address: '192.0.2.1' }] }) })
  const response = await getActivity(request())
  expect(await response.json()).toEqual({ activities: [{ id: 'session-a', action: 'Session started', timestamp: null, revoked: false, device: 'Example browser' }] })
  expect(new URL(mockFetch.mock.calls[0][0]).pathname).toBe('/api/v1/sessions/activity/recent')
})
