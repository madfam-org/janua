import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Janua Admin Middleware - Platform Operator Access Control
 *
 * SECURITY: This middleware enforces strict access control for Janua Admin.
 * Only authorized platform operators can access the admin interface.
 *
 * Authorization is based on:
 * 1. Email domain - must be from an allowed domain (@janua.dev, @madfam.io by default)
 * 2. User role - must have an admin-level role (superadmin, admin)
 *
 * Configure via environment variables:
 * - ALLOWED_ADMIN_DOMAINS: Comma-separated list of allowed email domains
 * - ALLOWED_ADMIN_ROLES: Comma-separated list of allowed roles
 */

// Allowed email domains (configurable via env)
const DEFAULT_DOMAINS = ['@janua.dev', '@madfam.io']
const ALLOWED_DOMAINS = process.env.ALLOWED_ADMIN_DOMAINS
  ? process.env.ALLOWED_ADMIN_DOMAINS.split(',').map((d) => d.trim())
  : DEFAULT_DOMAINS

// Allowed roles (configurable via env)
const DEFAULT_ROLES = ['superadmin', 'admin']
const ALLOWED_ROLES = process.env.ALLOWED_ADMIN_ROLES
  ? process.env.ALLOWED_ADMIN_ROLES.split(',').map((r) => r.trim())
  : DEFAULT_ROLES

/**
 * Check if an email is from an allowed domain
 */
function isAllowedDomain(email: string): boolean {
  return ALLOWED_DOMAINS.some((domain) => email.toLowerCase().endsWith(domain.toLowerCase()))
}

/**
 * Check if user has an allowed role
 */
function hasAllowedRole(rolesString: string | undefined): boolean {
  if (!rolesString) return false
  const userRoles = rolesString.split(',').map((r) => r.trim())
  return userRoles.some((role) => ALLOWED_ROLES.includes(role))
}

// Public paths that don't require authentication
const publicPaths = [
  '/login',
  '/auth/callback',
  '/api/auth',
  '/api/health',
  '/_next',
  '/favicon.ico',
  '/public',
]

function isPublicPath(pathname: string): boolean {
  return publicPaths.some(
    (path) => pathname === path || pathname.startsWith(path + '/')
  )
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Skip middleware for public paths
  if (isPublicPath(pathname)) {
    return addSecurityHeaders(NextResponse.next())
  }

  // Check for authentication token and user info
  const token = request.cookies.get('janua_token')?.value
  const userEmail = request.cookies.get('janua_admin_email')?.value
  const userRoles = request.cookies.get('janua_admin_roles')?.value

  // If no token, redirect to login
  if (!token) {
    if (pathname.startsWith('/api/')) {
      return new NextResponse(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // OPERATOR CHECK: Must have allowed domain AND allowed role
  const domainAllowed = userEmail ? isAllowedDomain(userEmail) : false
  const roleAllowed = hasAllowedRole(userRoles)

  if (!domainAllowed || !roleAllowed) {
    const reason = !domainAllowed
      ? `email domain not allowed: ${userEmail}`
      : `insufficient role: ${userRoles || 'none'}`
    console.warn(`[JANUA ADMIN SECURITY] Unauthorized access attempt - ${reason}`)

    if (pathname.startsWith('/api/')) {
      return new NextResponse(
        JSON.stringify({
          error: 'Forbidden',
          message: 'Admin access is restricted to authorized platform operators.',
        }),
        {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    }

    // Redirect unauthorized users to access denied page
    return NextResponse.redirect(new URL('/access-denied', request.url))
  }

  return addSecurityHeaders(NextResponse.next())
}

function addSecurityHeaders(response: NextResponse): NextResponse {
  const securityHeaders = {
    // Prevent clickjacking attacks
    'X-Frame-Options': 'DENY',

    // Prevent MIME type sniffing
    'X-Content-Type-Options': 'nosniff',

    // Enable XSS protection
    'X-XSS-Protection': '1; mode=block',

    // Control referrer information
    'Referrer-Policy': 'strict-origin-when-cross-origin',

    // Strict Content Security Policy
    'Content-Security-Policy': [
      "default-src 'self'",
      "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' data: https://fonts.gstatic.com",
      "img-src 'self' data: https:",
      `connect-src 'self' ${process.env.NEXT_PUBLIC_JANUA_API_URL || 'https://api.janua.dev'}`,
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
