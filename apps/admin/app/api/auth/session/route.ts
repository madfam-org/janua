import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { AdminSessionError, verifyAdminSession } from '@/lib/admin-session'

const legacyCookies = ['janua_admin_email', 'janua_admin_roles', 'janua_refresh_token']

function cookieOptions(maxAge: number) {
  return { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax' as const, path: '/', maxAge }
}

/** Exchange the SDK token for a host-only cookie after authoritative checks. */
export async function POST(request: NextRequest) {
  let token: unknown
  try {
    token = (await request.json())?.access_token
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }
  if (typeof token !== 'string' || !token.trim()) {
    return NextResponse.json({ error: 'access_token is required' }, { status: 400 })
  }

  try {
    const { user, expiresAt } = await verifyAdminSession(token.trim())
    const cookieStore = await cookies()
    cookieStore.set('janua_access_token', token.trim(), cookieOptions(Math.max(1, Math.floor(expiresAt - Date.now() / 1000))))
    // Retire the former unsigned authorization hints and unused refresh cookie.
    for (const name of legacyCookies) cookieStore.set(name, '', cookieOptions(0))
    return NextResponse.json({ ok: true, user }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    const status = error instanceof AdminSessionError ? error.status : 503
    return NextResponse.json(
      { error: status === 403 ? 'Admin access required' : status === 503 ? 'Authentication unavailable' : 'Invalid session' },
      { status, headers: { 'Cache-Control': 'no-store' } },
    )
  }
}

export async function DELETE() {
  const cookieStore = await cookies()
  for (const name of ['janua_access_token', ...legacyCookies]) {
    cookieStore.set(name, '', cookieOptions(0))
  }
  return NextResponse.json({ ok: true }, { headers: { 'Cache-Control': 'no-store' } })
}
