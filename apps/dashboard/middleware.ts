import { NextResponse } from 'next/server'
import { AUTH_COOKIE } from '@/lib/auth-keys'
import { isAccountSwitchRequest } from '@/lib/account-switch'
import type { NextRequest } from 'next/server'

/**
 * Validates JWT token structure (not signature - that's API-side)
 * Returns false for malformed tokens or tokens that appear expired
 */
function isValidTokenStructure(token: string | null | undefined): boolean {
  if (!token) return false

  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false

    // Decode the payload (base64url)
    const base64 = parts[1]!.replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8'))

    // Check for required claims
    if (!payload.exp || !payload.sub) return false

    // Check if token is expired (with 60 second buffer for clock skew)
    const now = Math.floor(Date.now() / 1000)
    if (payload.exp < now - 60) return false

    return true
  } catch {
    return false
  }
}

// Routes that don't require authentication
const PUBLIC_ROUTES = [
  '/login',
  '/auth/signup',
  '/auth/verify-email',
  '/api/',
  '/_next/',
  '/favicon.ico',
  '/icon',
  '/health',
]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Get token from cookie
  const token = request.cookies.get(AUTH_COOKIE)?.value
  const hasValidToken = isValidTokenStructure(token)
  const redirects = request.nextUrl.searchParams.getAll('redirect')
  const reasons = request.nextUrl.searchParams.getAll('reason')
  const invitationAccountSwitch = pathname === '/login' && redirects.length === 1 &&
    reasons.length === 1 && reasons[0] === 'session_expired' &&
    Array.from(request.nextUrl.searchParams.keys()).every(key => key === 'redirect' || key === 'reason') &&
    /^\/invitations\/accept\?token=[A-Za-z0-9_-]{32,128}$/.test(redirects[0]!)

  // If user is authenticated and trying to access login page, redirect to home
  // An explicit invitation account switch uses the existing expired-session
  // login flow, which clears the local session before a fresh sign-in.
  const deliberateAccountSwitch = pathname === '/login' && isAccountSwitchRequest(request.nextUrl.searchParams)
  if (pathname === '/login' && hasValidToken && !invitationAccountSwitch && !deliberateAccountSwitch) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  // Allow access to public routes
  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname.startsWith(route))
  if (isPublicRoute) {
    return NextResponse.next()
  }

  // Check if token exists and is structurally valid
  if (!hasValidToken) {
    // Clear the invalid cookie
    const response = NextResponse.redirect(new URL('/login', request.url))
    response.cookies.set(AUTH_COOKIE, '', {
      path: '/',
      expires: new Date(0),
    })

    // Add redirect param so user returns after login
    const loginUrl = new URL('/login', request.url)
    if (pathname !== '/') {
      // The invitation remains protected. Preserve only its bounded bearer
      // token through login, never an arbitrary query/return URL.
      const invitationTokens = request.nextUrl.searchParams.getAll('token')
      const invitationToken = invitationTokens[0]
      const returnPath = pathname === '/invitations/accept' &&
        invitationTokens.length === 1 && invitationToken &&
        /^[A-Za-z0-9_-]{32,128}$/.test(invitationToken)
        ? `${pathname}?${new URLSearchParams({ token: invitationToken })}`
        : pathname
      loginUrl.searchParams.set('redirect', returnPath)
    }

    // If token was present but invalid, indicate session expired
    if (token) {
      loginUrl.searchParams.set('reason', 'session_expired')
    }

    return NextResponse.redirect(loginUrl)
  }

  // Token appears valid (structure-wise), allow the request
  // Actual signature validation happens API-side
  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, icon (favicon files)
     * - public folder
     */
    '/((?!api|_next/static|_next/image|favicon.ico|icon|public).*)',
  ],
}
