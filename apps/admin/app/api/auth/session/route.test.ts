/** @jest-environment node */
import { NextRequest } from 'next/server'
import { POST, DELETE } from './route'
import { AdminSessionError, verifyAdminSession } from '@/lib/admin-session'

type CookieCall = { name: string; value: string; options: Record<string, unknown> }
const cookieCalls: CookieCall[] = []
jest.mock('next/headers', () => ({ cookies: jest.fn(async () => ({ set: (name: string, value: string, options: CookieCall['options']) => cookieCalls.push({ name, value, options }) })) }))
jest.mock('@/lib/admin-session', () => ({ ...jest.requireActual('@/lib/admin-session'), verifyAdminSession: jest.fn() }))
const verify = jest.mocked(verifyAdminSession)
const user = { id: 'operator-id', email: 'operator@janua.dev', is_admin: true as const }
const request = (body: unknown) => new NextRequest('https://admin.example/api/auth/session', { method: 'POST', body: JSON.stringify(body) })
const originalEnv = process.env.NODE_ENV
beforeEach(() => {
  cookieCalls.length = 0
  verify.mockReset().mockResolvedValue({ user, expiresAt: Math.floor(Date.now() / 1000) + 300 })
})
afterEach(() => { (process.env as Record<string, string | undefined>).NODE_ENV = originalEnv })

it('sets a token cookie only after authoritative validation and expires legacy role/email cookies', async () => {
  ;(process.env as Record<string, string | undefined>).NODE_ENV = 'production'
  const response = await POST(request({ access_token: 'access-token', email: 'spoof@other.example', roles: ['superadmin'], expires_at: 9999999999, refresh_token: 'ignored' }))
  expect(response.status).toBe(200)
  expect(await response.json()).toEqual({ ok: true, user })
  expect(response.headers.get('cache-control')).toBe('no-store')
  expect(verify).toHaveBeenCalledWith('access-token')
  expect(cookieCalls[0]).toMatchObject({ name: 'janua_access_token', value: 'access-token', options: { httpOnly: true, secure: true, sameSite: 'lax', path: '/' } })
  expect(cookieCalls[0].options.maxAge).toBeLessThanOrEqual(300)
  expect(cookieCalls.slice(1)).toHaveLength(3)
  for (const cookie of cookieCalls.slice(1)) expect(cookie).toMatchObject({ value: '', options: { maxAge: 0 } })
})
it.each([401, 403, 503] as const)('sets no cookies when validation fails with %s', async status => {
  verify.mockRejectedValue(new AdminSessionError(status))
  expect((await POST(request({ access_token: 'token' }))).status).toBe(status)
  expect(cookieCalls).toEqual([])
})
it.each([null, {}, { access_token: '' }, { access_token: 1 }])('rejects invalid bodies before authentication: %s', async body => {
  expect((await POST(request(body))).status).toBe(400)
  expect(verify).not.toHaveBeenCalled()
})
it('rejects malformed JSON before authentication', async () => {
  expect((await POST(new NextRequest('https://admin.example/api/auth/session', { method: 'POST', body: '{' }))).status).toBe(400)
  expect(verify).not.toHaveBeenCalled()
})
it('supports secure=false for local HTTP development only', async () => {
  ;(process.env as Record<string, string | undefined>).NODE_ENV = 'development'
  await POST(request({ access_token: 'token' }))
  expect(cookieCalls[0].options.secure).toBe(false)
})
it('expires the access and all legacy cookies on sign-out', async () => {
  expect((await DELETE()).status).toBe(200)
  expect(cookieCalls.map(call => call.name).sort()).toEqual(['janua_access_token', 'janua_admin_email', 'janua_admin_roles', 'janua_refresh_token'].sort())
  for (const call of cookieCalls) expect(call).toMatchObject({ value: '', options: { httpOnly: true, maxAge: 0, path: '/' } })
})
