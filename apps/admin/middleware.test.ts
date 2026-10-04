/** @jest-environment node */
import { NextRequest } from 'next/server'
import { middleware } from './middleware'
import { AdminSessionError, verifyAdminSession } from './lib/admin-session'

jest.mock('./lib/admin-session', () => ({
  ...jest.requireActual('./lib/admin-session'),
  verifyAdminSession: jest.fn(),
}))
const verify = jest.mocked(verifyAdminSession)
const request = (path = '/', cookie = '') => new NextRequest(`https://admin.example${path}`, { headers: { cookie } })

beforeEach(() => { verify.mockReset() })

it('never lets forged role/email cookies replace a valid token', async () => {
  verify.mockRejectedValue(new AdminSessionError(401))
  const response = await middleware(request('/', 'janua_access_token=forged; janua_admin_email=operator@janua.dev; janua_admin_roles=superadmin'))
  expect(verify).toHaveBeenCalledWith('forged')
  expect(response.headers.get('location')).toBe('https://admin.example/login')
})
it('ignores all identity cookies when authoritative validation succeeds', async () => {
  verify.mockResolvedValue({ user: { id: 'operator-id', email: 'operator@janua.dev', is_admin: true }, expiresAt: 9999999999 })
  const response = await middleware(request('/', 'janua_access_token=valid; janua_admin_roles=viewer; janua_admin_email=untrusted@other.example'))
  expect(response.status).toBe(200)
})
it('redirects non-platform admins to access denied', async () => {
  verify.mockRejectedValue(new AdminSessionError(403))
  const response = await middleware(request('/', 'janua_access_token=org-admin'))
  expect(response.headers.get('location')).toBe('https://admin.example/access-denied')
})
it('returns 503 and no-store when authoritative validation is unavailable', async () => {
  verify.mockRejectedValue(new AdminSessionError(503))
  const response = await middleware(request('/', 'janua_access_token=valid'))
  expect(response.status).toBe(503)
  expect(response.headers.get('cache-control')).toBe('no-store')
})
it('returns 401 on protected APIs with missing credentials', async () => {
  expect((await middleware(request('/api/metrics'))).status).toBe(401)
  expect(verify).not.toHaveBeenCalled()
})
it.each(['/login', '/access-denied', '/api/auth/session', '/api/health', '/health'])('keeps %s public without calling authentication', async path => {
  expect((await middleware(request(path))).status).toBe(200)
  expect(verify).not.toHaveBeenCalled()
})
