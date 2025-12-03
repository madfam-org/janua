import { NextResponse } from 'next/server'
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
  '/api/',
  '/_next/',
  '/favicon.ico',
  '/health',
]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow access to public routes
  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname.startsWith(route))
  if (isPublicRoute) {
    return NextResponse.next()
  }

  // Get token from cookie
  const token = request.cookies.get('janua_token')?.value

  // Check if token exists and is structurally valid
  if (!isValidTokenStructure(token)) {
    // Clear the invalid cookie
    const response = NextResponse.redirect(new URL('/login', request.url))
    response.cookies.set('janua_token', '', {
      path: '/',
      expires: new Date(0),
    })

    // Add redirect param so user returns after login
    const loginUrl = new URL('/login', request.url)
    if (pathname !== '/') {
      loginUrl.searchParams.set('redirect', pathname)
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
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!api|_next/static|_next/image|favicon.ico|public).*)',
  ],
}
