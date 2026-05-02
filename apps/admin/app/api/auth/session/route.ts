import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'

/**
 * Janua Admin — Session Cookie Bridge
 *
 * The browser-side <SignIn> component (and SSO callback) stores access /
 * refresh tokens in localStorage via the Janua SDK. The admin middleware,
 * however, gates protected routes on three HttpOnly cookies it reads from
 * `request.cookies`:
 *
 *   - janua_access_token  → bearer used for upstream API calls
 *   - janua_admin_email   → checked against the email domain allowlist
 *   - janua_admin_roles   → comma-separated role list parsed by middleware
 *
 * Setting HttpOnly cookies from JS in the browser is impossible by design,
 * so this route handler accepts the freshly-issued sign-in payload and
 * sets the three cookies server-side. The client invokes POST after a
 * successful sign-in (from the `afterSignIn` callback) and DELETE on
 * logout.
 *
 * Security:
 *   - HttpOnly  — JS cannot read the access token (mitigates XSS exfil)
 *   - Secure    — only sent over TLS in production
 *   - SameSite=Lax — protects against CSRF on top-level navigations while
 *     still allowing the dashboard SSO redirect flow to land properly
 *   - path '/'  — middleware runs on every protected route
 */

interface SessionPayload {
  access_token: string
  refresh_token?: string
  email: string
  roles?: string[] | string
  expires_at?: number | string
}

const ONE_DAY_SECONDS = 60 * 60 * 24

function normalizeRoles(roles: SessionPayload['roles']): string {
  if (!roles) return ''
  if (Array.isArray(roles)) return roles.map((r) => String(r).trim()).filter(Boolean).join(',')
  return String(roles).trim()
}

function deriveMaxAge(expiresAt: SessionPayload['expires_at']): number {
  if (expiresAt === undefined || expiresAt === null) return ONE_DAY_SECONDS
  const expiresMs = typeof expiresAt === 'string' ? Date.parse(expiresAt) : Number(expiresAt) * 1000
  if (!Number.isFinite(expiresMs)) return ONE_DAY_SECONDS
  const seconds = Math.floor((expiresMs - Date.now()) / 1000)
  if (seconds <= 0) return ONE_DAY_SECONDS
  // Cap at 30 days to avoid unbounded sessions.
  return Math.min(seconds, ONE_DAY_SECONDS * 30)
}

export async function POST(request: NextRequest) {
  let payload: SessionPayload
  try {
    payload = (await request.json()) as SessionPayload
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  const accessToken = typeof payload.access_token === 'string' ? payload.access_token.trim() : ''
  const email = typeof payload.email === 'string' ? payload.email.trim() : ''

  if (!accessToken || !email) {
    return NextResponse.json(
      { error: 'access_token and email are required' },
      { status: 400 }
    )
  }

  const roles = normalizeRoles(payload.roles)
  const maxAge = deriveMaxAge(payload.expires_at)
  const isProd = process.env.NODE_ENV === 'production'

  const cookieStore = await cookies()
  const baseOptions = {
    httpOnly: true,
    secure: isProd,
    sameSite: 'lax' as const,
    path: '/',
    maxAge,
  }

  cookieStore.set('janua_access_token', accessToken, baseOptions)
  cookieStore.set('janua_admin_email', email, baseOptions)
  cookieStore.set('janua_admin_roles', roles, baseOptions)

  if (payload.refresh_token && typeof payload.refresh_token === 'string') {
    cookieStore.set('janua_refresh_token', payload.refresh_token, {
      ...baseOptions,
      // Refresh tokens get a longer life, capped at 30 days.
      maxAge: ONE_DAY_SECONDS * 30,
    })
  }

  return NextResponse.json({ ok: true }, { status: 200 })
}

export async function DELETE() {
  const cookieStore = await cookies()
  const isProd = process.env.NODE_ENV === 'production'
  const expireOptions = {
    httpOnly: true,
    secure: isProd,
    sameSite: 'lax' as const,
    path: '/',
    maxAge: 0,
  }

  cookieStore.set('janua_access_token', '', expireOptions)
  cookieStore.set('janua_admin_email', '', expireOptions)
  cookieStore.set('janua_admin_roles', '', expireOptions)
  cookieStore.set('janua_refresh_token', '', expireOptions)

  return NextResponse.json({ ok: true }, { status: 200 })
}
