/**
 * @plinto/edge - Edge-fast JWT verification for Cloudflare Workers
 * Ultra-lightweight JWT verification optimized for edge environments
 */

import { importSPKI, jwtVerify, SignJWT, importPKCS8 } from 'jose';
import type { JWTPayload, JWTHeaderParameters } from 'jose';

export { JWTPayload };

/**
 * Plinto Edge configuration
 */
export interface EdgeConfig {
  publicKey?: string;
  jwksUrl?: string;
  issuer?: string;
  audience?: string;
  maxAge?: number;
  clockTolerance?: number;
}

/**
 * Verified token payload with Plinto-specific claims
 */
export interface VerifiedToken extends JWTPayload {
  userId?: string;
  email?: string;
  organizationId?: string;
  permissions?: string[];
  sessionId?: string;
}

/**
 * Verification result
 */
export interface VerificationResult {
  valid: boolean;
  payload?: VerifiedToken;
  error?: string;
  expired?: boolean;
}

/**
 * Cache interface for JWKS
 */
interface JWKSCache {
  keys: any;
  expires: number;
}

let jwksCache: JWKSCache | null = null;

/**
 * Main verification function for edge environments
 * Optimized for <50ms latency
 */
export async function verify(
  token: string,
  config: EdgeConfig
): Promise<VerificationResult> {
  try {
    // Fast path: Direct public key verification
    if (config.publicKey) {
      return await verifyWithPublicKey(token, config);
    }

    // JWKS verification (with caching)
    if (config.jwksUrl) {
      return await verifyWithJWKS(token, config);
    }

    return {
      valid: false,
      error: 'No public key or JWKS URL provided',
    };
  } catch (error: any) {
    // Check if token is expired
    if (error.code === 'ERR_JWT_EXPIRED') {
      return {
        valid: false,
        error: 'Token expired',
        expired: true,
      };
    }

    return {
      valid: false,
      error: error.message || 'Verification failed',
    };
  }
}

/**
 * Verify token with a direct public key
 */
async function verifyWithPublicKey(
  token: string,
  config: EdgeConfig
): Promise<VerificationResult> {
  const publicKey = await importSPKI(config.publicKey!, 'RS256');
  
  const { payload } = await jwtVerify(token, publicKey, {
    issuer: config.issuer,
    audience: config.audience,
    maxTokenAge: config.maxAge,
    clockTolerance: config.clockTolerance,
  });

  return {
    valid: true,
    payload: payload as VerifiedToken,
  };
}

/**
 * Verify token with JWKS (with caching for edge performance)
 */
async function verifyWithJWKS(
  token: string,
  config: EdgeConfig
): Promise<VerificationResult> {
  // Get JWKS (from cache if available)
  const jwks = await getJWKS(config.jwksUrl!);
  
  // Extract kid from token header
  const [header] = token.split('.');
  const decodedHeader = JSON.parse(atob(header)) as JWTHeaderParameters;
  const kid = decodedHeader.kid;

  if (!kid) {
    return {
      valid: false,
      error: 'No kid in token header',
    };
  }

  // Find matching key
  const key = jwks.keys.find((k: any) => k.kid === kid);
  if (!key) {
    return {
      valid: false,
      error: 'No matching key found in JWKS',
    };
  }

  // Import and verify
  const publicKey = await importSPKI(key.x5c[0], key.alg);
  
  const { payload } = await jwtVerify(token, publicKey, {
    issuer: config.issuer,
    audience: config.audience,
    maxTokenAge: config.maxAge,
    clockTolerance: config.clockTolerance,
  });

  return {
    valid: true,
    payload: payload as VerifiedToken,
  };
}

/**
 * Get JWKS with caching
 */
async function getJWKS(url: string): Promise<any> {
  // Check cache
  if (jwksCache && jwksCache.expires > Date.now()) {
    return jwksCache.keys;
  }

  // Fetch JWKS
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch JWKS: ${response.statusText}`);
  }

  const jwks = await response.json();

  // Cache for 1 hour
  jwksCache = {
    keys: jwks,
    expires: Date.now() + 3600000,
  };

  return jwks;
}

/**
 * Express/Koa style middleware for edge environments
 */
export function middleware(config: EdgeConfig) {
  return async (request: Request): Promise<Response | null> => {
    const authHeader = request.headers.get('Authorization');
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return new Response('Unauthorized', { status: 401 });
    }

    const token = authHeader.substring(7);
    const result = await verify(token, config);

    if (!result.valid) {
      return new Response(result.error || 'Unauthorized', { 
        status: result.expired ? 401 : 403 
      });
    }

    // Token is valid, continue (return null to proceed)
    // Attach payload to request for downstream use
    (request as any).user = result.payload;
    return null;
  };
}

/**
 * Cloudflare Worker specific handler
 */
export function createWorkerHandler(config: EdgeConfig) {
  return {
    async fetch(request: Request, env: any, ctx: any): Promise<Response> {
      // Run middleware
      const middlewareResponse = await middleware(config)(request);
      if (middlewareResponse) {
        return middlewareResponse;
      }

      // Token is valid, handle the request
      const user = (request as any).user;
      
      return new Response(JSON.stringify({
        message: 'Authenticated',
        user: {
          id: user.userId,
          email: user.email,
          organizationId: user.organizationId,
        },
      }), {
        headers: { 'Content-Type': 'application/json' },
      });
    },
  };
}

/**
 * Helper to extract token from various sources
 */
export function extractToken(request: Request): string | null {
  // Check Authorization header
  const authHeader = request.headers.get('Authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }

  // Check cookie
  const cookie = request.headers.get('Cookie');
  if (cookie) {
    const match = cookie.match(/plinto_token=([^;]+)/);
    if (match) {
      return match[1];
    }
  }

  // Check query parameter (for WebSocket upgrades)
  const url = new URL(request.url);
  const token = url.searchParams.get('token');
  if (token) {
    return token;
  }

  return null;
}

/**
 * Sign a token (useful for testing or edge-based token generation)
 */
export async function sign(
  payload: JWTPayload,
  privateKey: string,
  options?: {
    expiresIn?: string;
    issuer?: string;
    audience?: string;
    kid?: string;
  }
): Promise<string> {
  const key = await importPKCS8(privateKey, 'RS256');
  
  let jwt = new SignJWT(payload)
    .setProtectedHeader({ 
      alg: 'RS256',
      ...(options?.kid && { kid: options.kid }),
    })
    .setIssuedAt();

  if (options?.expiresIn) {
    jwt = jwt.setExpirationTime(options.expiresIn);
  }
  if (options?.issuer) {
    jwt = jwt.setIssuer(options.issuer);
  }
  if (options?.audience) {
    jwt = jwt.setAudience(options.audience);
  }

  return await jwt.sign(key);
}

/**
 * Performance metrics for monitoring
 */
export class VerificationMetrics {
  private static timings: number[] = [];

  static record(duration: number): void {
    this.timings.push(duration);
    // Keep only last 100 timings
    if (this.timings.length > 100) {
      this.timings.shift();
    }
  }

  static getStats() {
    if (this.timings.length === 0) {
      return { avg: 0, min: 0, max: 0, p95: 0 };
    }

    const sorted = [...this.timings].sort((a, b) => a - b);
    const avg = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const p95Index = Math.floor(sorted.length * 0.95);

    return {
      avg: Math.round(avg),
      min: sorted[0],
      max: sorted[sorted.length - 1],
      p95: sorted[p95Index],
    };
  }
}

/**
 * Timed verification wrapper for performance monitoring
 */
export async function verifyWithMetrics(
  token: string,
  config: EdgeConfig
): Promise<VerificationResult> {
  const start = Date.now();
  const result = await verify(token, config);
  const duration = Date.now() - start;
  
  VerificationMetrics.record(duration);
  
  return result;
}

// Export version
export const VERSION = '0.1.0';