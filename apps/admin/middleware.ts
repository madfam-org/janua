import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

import { AdminSessionError, verifyAdminSession } from './lib/admin-session'

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
  const { pathname } = request.nextUrl
  if (isPublicPath(pathname)) return addSecurityHeaders(NextResponse.next())

  const token = request.cookies.get('janua_access_token')?.value
  try {
    if (!token) throw new AdminSessionError(401)
    await verifyAdminSession(token)
    return addSecurityHeaders(NextResponse.next())
  } catch (error) {
    const status = error instanceof AdminSessionError ? error.status : 503
    // Never log request cookies, tokens, claims or identity records.
    if (pathname.startsWith('/api/') || status === 503) {
      return addSecurityHeaders(NextResponse.json(
        { error: status === 403 ? 'Forbidden' : status === 503 ? 'Authentication unavailable' : 'Unauthorized' },
        { status, headers: { 'Cache-Control': 'no-store' } },
      ))
    }
    return addSecurityHeaders(NextResponse.redirect(new URL(status === 403 ? '/access-denied' : '/login', request.url)))
  }
}

function addSecurityHeaders(response: NextResponse): NextResponse {
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
    'Content-Security-Policy': [
      "default-src 'self'",
      `script-src 'self'${process.env.NODE_ENV === 'development' ? " 'unsafe-eval'" : ''} 'unsafe-inline' https://static.cloudflareinsights.com`,
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' data: https://fonts.gstatic.com",
      "img-src 'self' data: https:",
      `connect-src 'self' ${process.env.NEXT_PUBLIC_JANUA_API_URL || 'https://api.janua.dev'} https://cloudflareinsights.com`,
      "frame-ancestors 'none'",
    ].join('; '),

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
