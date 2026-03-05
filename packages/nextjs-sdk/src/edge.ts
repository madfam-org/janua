/**
 * Edge-compatible JWT verification for Next.js middleware
 *
 * Uses jose (edge-runtime compatible) for lightweight JWT verification.
 * Lighter than the full createJanuaMiddleware — just verifies JWTs.
 */
import * as jose from 'jose';

export interface EdgeMiddlewareConfig {
  /** JWKS endpoint URL for fetching public keys */
  jwksUrl: string;
  /** Expected JWT issuer (optional) */
  issuer?: string;
  /** Expected JWT audience (optional) */
  audience?: string;
  /** Cookie name containing the access token (default: 'janua_session') */
  cookieName?: string;
  /** Header name for Bearer token (default: 'authorization') */
  headerName?: string;
  /** Clock tolerance in seconds (default: 5) */
  clockTolerance?: number;
}

export interface VerifiedToken {
  /** Decoded JWT payload */
  payload: jose.JWTPayload;
  /** User ID from the 'sub' claim */
  userId: string | undefined;
  /** Token expiration time */
  expiresAt: Date | undefined;
}

/**
 * Create an edge-compatible JWT verification middleware helper.
 *
 * Usage in Next.js middleware:
 * ```typescript
 * import { createEdgeMiddleware } from '@janua/nextjs-sdk/edge';
 *
 * const verify = createEdgeMiddleware({
 *   jwksUrl: 'https://api.janua.dev/.well-known/jwks.json',
 * });
 *
 * export async function middleware(request: NextRequest) {
 *   const result = await verify(request);
 *   if (!result.authenticated) {
 *     return NextResponse.redirect(new URL('/login', request.url));
 *   }
 *   // result.token.userId, result.token.payload available
 * }
 * ```
 */
export function createEdgeMiddleware(config: EdgeMiddlewareConfig) {
  const {
    jwksUrl,
    issuer,
    audience,
    cookieName = 'janua_session',
    headerName = 'authorization',
    clockTolerance = 5,
  } = config;

  const JWKS = jose.createRemoteJWKSet(new URL(jwksUrl));

  return async function verifyRequest(
    request: Request & { cookies?: { get(name: string): { value: string } | undefined } }
  ): Promise<{ authenticated: true; token: VerifiedToken } | { authenticated: false; error: string }> {
    let jwt: string | undefined;

    // Try Authorization header first
    const authHeader = request.headers.get(headerName);
    if (authHeader?.startsWith('Bearer ')) {
      jwt = authHeader.slice(7);
    }

    // Fall back to cookie
    if (!jwt && request.cookies) {
      const cookie = request.cookies.get(cookieName);
      if (cookie) {
        jwt = cookie.value;
      }
    }

    if (!jwt) {
      return { authenticated: false, error: 'No token found' };
    }

    try {
      const verifyOptions: jose.JWTVerifyOptions = { clockTolerance };
      if (issuer) verifyOptions.issuer = issuer;
      if (audience) verifyOptions.audience = audience;

      const { payload } = await jose.jwtVerify(jwt, JWKS, verifyOptions);

      return {
        authenticated: true,
        token: {
          payload,
          userId: payload.sub,
          expiresAt: payload.exp ? new Date(payload.exp * 1000) : undefined,
        },
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Token verification failed';
      return { authenticated: false, error: message };
    }
  };
}
