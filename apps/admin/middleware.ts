import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

import { AdminSessionError, verifyAdminSession } from './lib/admin-session'
import { consoleCsp, consoleSessionCookie, type ConsoleRuntimeConfig } from '@janua/ui/console-runtime'
import { readConsoleConfig } from './lib/console-runtime.server'

// Public paths that don't require authentication
const publicPaths = [
  '/login',
  '/access-denied',
  '/auth/callback',
  '/api/auth',
  '/api/health',
  '/health',
  '/_next',
  '/favicon.ico',
  '/public',
]

function isPublicPath(pathname: string): boolean {
  return publicPaths.some(
    (path) => pathname === path || pathname.startsWith(path + '/')
  )
}

export async function middleware(request: NextRequest) {
  let runtime
  try { runtime = readConsoleConfig() } catch {
    return NextResponse.json({ error: 'Console configuration unavailable' }, {
      status: 503, headers: { 'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'" },
    })
  }
  const { pathname } = request.nextUrl
  if (isPublicPath(pathname)) return addSecurityHeaders(NextResponse.next(), runtime)

  const token = request.cookies.get(consoleSessionCookie(runtime))?.value
  try {
    if (!token) throw new AdminSessionError(401)
    await verifyAdminSession(token)
    return addSecurityHeaders(NextResponse.next(), runtime)
  } catch (error) {
    const status = error instanceof AdminSessionError ? error.status : 503
    // Never log request cookies, tokens, claims or identity records.
    if (pathname.startsWith('/api/') || status === 503) {
      return addSecurityHeaders(NextResponse.json(
        { error: status === 403 ? 'Forbidden' : status === 503 ? 'Authentication unavailable' : 'Unauthorized' },
        { status, headers: { 'Cache-Control': 'no-store' } },
      ), runtime)
    }
    return addSecurityHeaders(NextResponse.redirect(new URL(status === 403 ? '/access-denied' : '/login', request.url)), runtime)
  }
}

function addSecurityHeaders(response: NextResponse, runtime: ConsoleRuntimeConfig): NextResponse {
  const securityHeaders = {
    // Prevent clickjacking attacks
    'X-Frame-Options': 'DENY',

    // Prevent MIME type sniffing
    'X-Content-Type-Options': 'nosniff',

    // Disable legacy XSS filter (modern CSP is preferred; the filter can introduce vulnerabilities)
    'X-XSS-Protection': '0',

    // Control referrer information
    'Referrer-Policy': 'strict-origin-when-cross-origin',

    // Strict Content Security Policy
    'Content-Security-Policy': consoleCsp(runtime),
    'Cache-Control': response.headers.get('Cache-Control') || 'private, no-store',

    // Restrict browser features
    'Permissions-Policy': [
      'geolocation=()',
      'microphone=()',
      'camera=()',
      'payment=()',
      'usb=()',
    ].join(', '),

    // HSTS in production
    ...(process.env.NODE_ENV === 'production' && {
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
    }),
  }

  Object.entries(securityHeaders).forEach(([key, value]) => {
    if (value) {
      response.headers.set(key, value)
    }
  })

  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|public).*)'],
}
