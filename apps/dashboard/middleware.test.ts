import type { NextRequest } from 'next/server'

jest.mock('next/server', () => ({
  NextResponse: {
    redirect: (url: URL) => ({ destination: url, cookies: { set: jest.fn() } }),
    next: () => ({ allowed: true }),
  },
}))
import { middleware } from './middleware'

const token = 'b'.repeat(43)
function request(path: string, cookie?: string): NextRequest {
  const url = new URL(path, 'https://app.janua.dev')
  return { url: url.href, nextUrl: url, cookies: { get: () => cookie ? { value: cookie } : undefined } } as unknown as NextRequest
}
function destination(path: string, cookie?: string): URL {
  return (middleware(request(path, cookie)) as unknown as { destination: URL }).destination
}
const validCookie = () => `header.${Buffer.from(JSON.stringify({ sub: 'fixture-self', exp: Math.floor(Date.now() / 1000) + 120 })).toString('base64url')}.signature`

describe('middleware invitation login return', () => {
  it('keeps exact invitation token through protected login and removes unrelated URL controls', () => {
    const login = destination(`/invitations/accept?token=${token}&redirect=https://foreign.invalid&organization=fixture`)
    expect(login.origin).toBe('https://app.janua.dev')
    expect(login.pathname).toBe('/login')
    expect(login.searchParams.get('redirect')).toBe(`/invitations/accept?token=${token}`)
    expect([...login.searchParams.keys()]).toEqual(['redirect'])
  })
  it.each(['../escape', 'https://foreign.invalid', 'a'.repeat(129), '', 'x%252fy'])('drops invalid token %s from the login return', value => {
    expect(destination(`/invitations/accept?token=${encodeURIComponent(value)}`).searchParams.get('redirect')).toBe('/invitations/accept')
  })
  it('refuses duplicate invitation tokens rather than choosing one', () => {
    expect(destination(`/invitations/accept?token=${token}&token=${token}`).searchParams.get('redirect')).toBe('/invitations/accept')
  })
  it('keeps expired-session reason with the invitation return', () => {
    const login = destination(`/invitations/accept?token=${token}`, 'not-a-jwt')
    expect(login.searchParams.get('redirect')).toBe(`/invitations/accept?token=${token}`)
    expect(login.searchParams.get('reason')).toBe('session_expired')
  })
  it('allows an explicit invitation account switch through login even with a valid old cookie', () => {
    const query = new URLSearchParams({ redirect: `/invitations/accept?token=${token}`, reason: 'session_expired' })
    expect(middleware(request(`/login?${query}`, validCookie()))).toEqual({ allowed: true })
  })
  it.each([
    { redirect: `https://app.janua.dev/invitations/accept?token=${token}`, reason: 'session_expired' },
    { redirect: `//foreign.invalid/invitations/accept?token=${token}`, reason: 'session_expired' },
    { redirect: `/invitations/accept?token=${token}&role=owner`, reason: 'session_expired' },
    { redirect: `/organizations?token=${token}`, reason: 'session_expired' },
    { redirect: `/invitations/accept?token=${token}`, reason: 'other' },
  ])('preserves ordinary authenticated-login redirect for unsafe/non-invitation account switch', query => {
    expect(destination(`/login?${new URLSearchParams(query)}`, validCookie()).pathname).toBe('/')
  })
  it('refuses duplicate/extra login-return controls for authenticated account switching', () => {
    const query = new URLSearchParams({ redirect: `/invitations/accept?token=${token}`, reason: 'session_expired' })
    expect(destination(`/login?${query}&redirect=${encodeURIComponent(`/invitations/accept?token=${token}`)}`, validCookie()).pathname).toBe('/')
    expect(destination(`/login?${query}&reason=session_expired`, validCookie()).pathname).toBe('/')
    expect(destination(`/login?${query}&next=/`, validCookie()).pathname).toBe('/')
  })
  it('preserves existing non-invitation redirect and public-route behavior', () => {
    expect(destination(`/organizations?token=${token}`).searchParams.get('redirect')).toBe('/organizations')
    expect(destination(`/invitations/accept/other?token=${token}`).searchParams.get('redirect')).toBe('/invitations/accept/other')
    expect(middleware(request('/auth/signup'))).toEqual({ allowed: true })
    expect(middleware(request(`/login?redirect=%2Finvitations%2Faccept%3Ftoken%3D${token}`))).toEqual({ allowed: true })
    expect(destination('/login', validCookie()).pathname).toBe('/')
    expect(middleware(request(`/invitations/accept?token=${token}`, validCookie()))).toEqual({ allowed: true })
    expect(destination('/').searchParams.has('redirect')).toBe(false)
  })
})
