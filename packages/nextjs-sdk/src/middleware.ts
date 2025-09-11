import { NextRequest, NextResponse } from 'next/server';
import { jwtVerify } from 'jose';

export interface PlintoMiddlewareConfig {
  jwtSecret: string;
  publicRoutes?: string[];
  protectedRoutes?: string[];
  redirectUrl?: string;
  cookieName?: string;
}

export function createPlintoMiddleware(config: PlintoMiddlewareConfig) {
  const {
    jwtSecret,
    publicRoutes = ['/login', '/signup', '/forgot-password'],
    protectedRoutes = [],
    redirectUrl = '/login',
    cookieName = 'plinto-session',
  } = config;

  const secret = new TextEncoder().encode(jwtSecret);

  return async function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;
    
    // Check if route is public
    const isPublicRoute = publicRoutes.some(route => {
      if (route.endsWith('*')) {
        return pathname.startsWith(route.slice(0, -1));
      }
      return pathname === route;
    });

    // Check if route is protected
    const isProtectedRoute = protectedRoutes.length > 0
      ? protectedRoutes.some(route => {
          if (route.endsWith('*')) {
            return pathname.startsWith(route.slice(0, -1));
          }
          return pathname === route;
        })
      : !isPublicRoute; // If no protected routes specified, all non-public routes are protected

    // If public route, allow access
    if (isPublicRoute) {
      return NextResponse.next();
    }

    // If protected route, check authentication
    if (isProtectedRoute) {
      const sessionCookie = request.cookies.get(cookieName);
      
      if (!sessionCookie) {
        const redirectTo = new URL(redirectUrl, request.url);
        redirectTo.searchParams.set('from', pathname);
        return NextResponse.redirect(redirectTo);
      }

      try {
        await jwtVerify(sessionCookie.value, secret);
        return NextResponse.next();
      } catch {
        // Invalid or expired token
        const redirectTo = new URL(redirectUrl, request.url);
        redirectTo.searchParams.set('from', pathname);
        
        const response = NextResponse.redirect(redirectTo);
        response.cookies.delete(cookieName);
        return response;
      }
    }

    return NextResponse.next();
  };
}

// Pre-configured middleware for common use cases
export function withAuth(
  config: Omit<PlintoMiddlewareConfig, 'jwtSecret'> & { jwtSecret?: string }
) {
  const jwtSecret = config.jwtSecret || process.env.PLINTO_JWT_SECRET;
  
  if (!jwtSecret) {
    throw new Error(
      'JWT secret is required. Set PLINTO_JWT_SECRET environment variable or pass jwtSecret in config.'
    );
  }

  return createPlintoMiddleware({ ...config, jwtSecret });
}

// Middleware matcher configuration
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!api|_next/static|_next/image|favicon.ico|public).*)',
  ],
};