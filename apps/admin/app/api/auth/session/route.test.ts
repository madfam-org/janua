/**
 * @jest-environment node
 */

import { POST, DELETE } from './route'

// Capture every cookies().set() call so we can assert flags.
type CookieCall = {
  name: string
  value: string
  options: {
    httpOnly?: boolean
    secure?: boolean
    sameSite?: 'lax' | 'strict' | 'none'
    path?: string
    maxAge?: number
  }
}

const cookieCalls: CookieCall[] = []

jest.mock('next/headers', () => ({
  cookies: jest.fn(async () => ({
    set: (name: string, value: string, options: CookieCall['options']) => {
      cookieCalls.push({ name, value, options })
    },
  })),
}))

jest.mock('next/server', () => {
  class FakeNextResponse {
    body: unknown
    status: number
    constructor(body: unknown, init?: { status?: number }) {
      this.body = body
      this.status = init?.status ?? 200
    }
    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init)
    }
  }
  return { NextResponse: FakeNextResponse }
})

function makeRequest(body: unknown, opts: { malformed?: boolean } = {}): any {
  return {
    json: jest.fn(async () => {
      if (opts.malformed) throw new Error('invalid json')
      return body
    }),
  }
}

describe('POST /api/auth/session', () => {
  beforeEach(() => {
    cookieCalls.length = 0
    delete (process.env as any).NODE_ENV
  })

  it('sets HttpOnly, Lax, path=/ cookies for access token, email, and roles', async () => {
    ;(process.env as any).NODE_ENV = 'production'
    const future = Math.floor(Date.now() / 1000) + 3600

    const res: any = await POST(
      makeRequest({
        access_token: 'jwt-abc',
        refresh_token: 'refresh-xyz',
        email: 'ops@janua.dev',
        roles: ['superadmin', 'admin'],
        expires_at: future,
      })
    )

    expect(res.status).toBe(200)
    expect(res.body).toEqual({ ok: true })

    const byName = Object.fromEntries(cookieCalls.map((c) => [c.name, c]))

    expect(byName.janua_access_token.value).toBe('jwt-abc')
    expect(byName.janua_access_token.options).toMatchObject({
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      path: '/',
    })
    expect(byName.janua_access_token.options.maxAge).toBeGreaterThan(0)
    expect(byName.janua_access_token.options.maxAge).toBeLessThanOrEqual(3600)

    expect(byName.janua_admin_email.value).toBe('ops@janua.dev')
    expect(byName.janua_admin_email.options).toMatchObject({
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      path: '/',
    })

    expect(byName.janua_admin_roles.value).toBe('superadmin,admin')
    expect(byName.janua_admin_roles.options).toMatchObject({
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      path: '/',
    })

    expect(byName.janua_refresh_token.value).toBe('refresh-xyz')
    expect(byName.janua_refresh_token.options.httpOnly).toBe(true)
  })

  it('marks Secure=false outside production so dev http://localhost works', async () => {
    ;(process.env as any).NODE_ENV = 'development'

    await POST(
      makeRequest({
        access_token: 'jwt-abc',
        email: 'ops@janua.dev',
        roles: ['admin'],
      })
    )

    const access = cookieCalls.find((c) => c.name === 'janua_access_token')!
    expect(access.options.secure).toBe(false)
    expect(access.options.httpOnly).toBe(true)
    expect(access.options.sameSite).toBe('lax')
  })

  it('accepts comma-separated roles string and trims whitespace', async () => {
    await POST(
      makeRequest({
        access_token: 'jwt',
        email: 'ops@janua.dev',
        roles: ' superadmin , admin ',
      })
    )

    const roles = cookieCalls.find((c) => c.name === 'janua_admin_roles')!
    expect(roles.value).toBe('superadmin , admin')
  })

  it('omits the refresh-token cookie when no refresh_token is supplied', async () => {
    await POST(
      makeRequest({
        access_token: 'jwt',
        email: 'ops@janua.dev',
        roles: ['admin'],
      })
    )

    expect(cookieCalls.find((c) => c.name === 'janua_refresh_token')).toBeUndefined()
  })

  it('rejects requests missing access_token', async () => {
    const res: any = await POST(
      makeRequest({ email: 'ops@janua.dev', roles: ['admin'] })
    )
    expect(res.status).toBe(400)
    expect(cookieCalls).toHaveLength(0)
  })

  it('rejects requests missing email', async () => {
    const res: any = await POST(makeRequest({ access_token: 'jwt' }))
    expect(res.status).toBe(400)
    expect(cookieCalls).toHaveLength(0)
  })

  it('rejects malformed JSON bodies', async () => {
    const res: any = await POST(makeRequest(undefined, { malformed: true }))
    expect(res.status).toBe(400)
    expect(cookieCalls).toHaveLength(0)
  })

  it('falls back to a 1-day maxAge when expires_at is missing', async () => {
    await POST(
      makeRequest({
        access_token: 'jwt',
        email: 'ops@janua.dev',
        roles: ['admin'],
      })
    )

    const access = cookieCalls.find((c) => c.name === 'janua_access_token')!
    expect(access.options.maxAge).toBe(60 * 60 * 24)
  })
})

describe('DELETE /api/auth/session', () => {
  beforeEach(() => {
    cookieCalls.length = 0
  })

  it('expires all four admin cookies with maxAge=0 and HttpOnly=true', async () => {
    const res: any = await DELETE()
    expect(res.status).toBe(200)
    expect(res.body).toEqual({ ok: true })

    const names = cookieCalls.map((c) => c.name).sort()
    expect(names).toEqual(
      [
        'janua_access_token',
        'janua_admin_email',
        'janua_admin_roles',
        'janua_refresh_token',
      ].sort()
    )

    for (const call of cookieCalls) {
      expect(call.value).toBe('')
      expect(call.options.maxAge).toBe(0)
      expect(call.options.httpOnly).toBe(true)
      expect(call.options.sameSite).toBe('lax')
      expect(call.options.path).toBe('/')
    }
  })
})
