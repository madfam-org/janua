import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { AdminSessionError, verifyAdminSession } from '@/lib/admin-session'
import { consoleSessionCookie } from '@janua/ui/console-runtime'
import { readConsoleConfig } from '@/lib/console-runtime.server'

const legacyCookies = ['janua_admin_email', 'janua_admin_roles', 'janua_refresh_token']

function cookieOptions(maxAge: number, environment: string) {
  return { httpOnly: true, secure: environment !== 'development', sameSite: 'lax' as const, path: '/', maxAge }
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
    const runtime = readConsoleConfig()
    const { user, expiresAt } = await verifyAdminSession(token.trim())
    const cookieStore = await cookies()
    cookieStore.set(consoleSessionCookie(runtime), token.trim(), cookieOptions(Math.max(1, Math.floor(expiresAt - Date.now() / 1000)), runtime.environment))
    // Retire the former unsigned authorization hints and unused refresh cookie.
    if (runtime.environment !== 'staging') for (const name of legacyCookies) cookieStore.set(name, '', cookieOptions(0, runtime.environment))
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
  let runtime
  try { runtime = readConsoleConfig() } catch {
    return NextResponse.json({ error: 'Console configuration unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
  const cookieStore = await cookies()
  for (const name of [consoleSessionCookie(runtime), ...(runtime.environment === 'staging' ? [] : legacyCookies)]) {
    cookieStore.set(name, '', cookieOptions(0, runtime.environment))
  }
  return NextResponse.json({ ok: true }, { headers: { 'Cache-Control': 'no-store' } })
}
