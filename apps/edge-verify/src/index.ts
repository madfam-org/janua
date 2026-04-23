/**
 * Janua Edge Verification Worker
 * High-performance JWT verification at the edge
 */

import { verifyJWT } from './jwt'
import { JWKSCache } from './jwks'
import { RateLimiter } from './rate-limiter'

export interface Env {
  JWKS_CACHE: KVNamespace
  RATE_LIMITER: DurableObjectNamespace
  ENVIRONMENT: string
  JWKS_URL: string
  JWT_AUDIENCE: string
  JWT_ISSUER: string
  // Comma-separated list of origins or wildcard patterns
  // (e.g. "https://app.madfam.io,https://*.madfam.io,https://partner.com").
  // When unset, falls back to a conservative *.madfam.io allowlist.
  CORS_ALLOWED_ORIGINS?: string
}

// Default allowlist used when CORS_ALLOWED_ORIGINS is not provided. Keep this
// in sync with Enclii ingress and known MADFAM product domains.
const DEFAULT_ALLOWED_ORIGINS: readonly string[] = [
  'https://*.madfam.io',
  'https://*.janua.dev',
  // Ecosystem partner domains that talk to the edge verifier from the browser.
  'https://*.enclii.dev',
  'https://*.rondel.io',
  'https://*.forgesight.quest',
  'https://*.dhan.am',
  'https://*.karafiel.mx',
  'https://*.tezca.mx',
  'https://*.selva.town',
  'https://*.routecraft.app',
]

function parseAllowlist(env: Env): readonly string[] {
  const raw = (env.CORS_ALLOWED_ORIGINS ?? '').trim()
  if (!raw) return DEFAULT_ALLOWED_ORIGINS
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

function matchesPattern(origin: string, pattern: string): boolean {
  // Exact match covers "https://app.madfam.io" style entries.
  if (pattern === origin) return true
  // Wildcard host support, e.g. "https://*.madfam.io" matches
  // "https://admin.madfam.io" but NOT "https://evil-madfam.io".
  if (pattern.includes('*')) {
    const escaped = pattern
      .replace(/[.+^${}()|[\]\\]/g, '\\$&')
      .replace(/\*/g, '[A-Za-z0-9-]+')
    return new RegExp(`^${escaped}$`).test(origin)
  }
  return false
}

function resolveCors(env: Env, origin: string | null): Record<string, string> {
  const base: Record<string, string> = {
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  }
  if (!origin) return base
  const allowlist = parseAllowlist(env)
  const allowed = allowlist.some((p) => matchesPattern(origin, p))
  if (!allowed) return base
  return {
    ...base,
    'Access-Control-Allow-Origin': origin,
  }
}

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    // Start timing
    const startTime = Date.now()

    // CORS headers (audit 2026-04-23 H5: no wildcards on the edge verifier).
    const origin = request.headers.get('Origin')
    const corsHeaders = resolveCors(env, origin)

    // Handle OPTIONS
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders })
    }

    try {
      // Extract token from Authorization header
      const authorization = request.headers.get('Authorization')
      if (!authorization?.startsWith('Bearer ')) {
        return jsonResponse(
          { error: 'Missing or invalid Authorization header' },
          401,
          corsHeaders
        )
      }

      const token = authorization.slice(7)

      // Rate limiting
      const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1'
      const rateLimitId = env.RATE_LIMITER.idFromName(clientIP)
      const rateLimiter = env.RATE_LIMITER.get(rateLimitId)
      
      const rateLimitResponse = await rateLimiter.fetch(
        new Request('http://rate-limiter/check', {
          method: 'POST',
          body: JSON.stringify({ key: clientIP, limit: 100, window: 60 })
        })
      )

      if (!rateLimitResponse.ok) {
        const remaining = rateLimitResponse.headers.get('X-RateLimit-Remaining')
        const reset = rateLimitResponse.headers.get('X-RateLimit-Reset')
        
        return jsonResponse(
          { error: 'Rate limit exceeded' },
          429,
          {
            ...corsHeaders,
            'X-RateLimit-Remaining': remaining || '0',
            'X-RateLimit-Reset': reset || '',
            'Retry-After': '60'
          }
        )
      }

      // Get JWKS (with caching)
      const jwksCache = new JWKSCache(env.JWKS_CACHE)
      const jwks = await jwksCache.get(
        env.JWKS_URL || 'https://janua.dev/.well-known/jwks.json'
      )

      if (!jwks) {
        return jsonResponse(
          { error: 'Failed to fetch JWKS' },
          500,
          corsHeaders
        )
      }

      // Verify JWT
      const payload = await verifyJWT(token, jwks, {
        audience: env.JWT_AUDIENCE || 'janua.dev',
        issuer: env.JWT_ISSUER || 'https://janua.dev',
      })

      // Check if token is revoked (optional, requires additional KV lookup)
      const revoked = await env.JWKS_CACHE.get(`revoked:${payload.jti}`)
      if (revoked) {
        return jsonResponse(
          { error: 'Token has been revoked' },
          401,
          corsHeaders
        )
      }

      // Calculate response time
      const responseTime = Date.now() - startTime

      // Return verified claims
      return jsonResponse(
        {
          valid: true,
          claims: payload,
          verified_at: new Date().toISOString(),
          response_time_ms: responseTime
        },
        200,
        {
          ...corsHeaders,
          'X-Response-Time': `${responseTime}ms`,
          'Cache-Control': 'private, max-age=60'
        }
      )

    } catch (error: any) {
      console.error('Verification error:', error)
      
      // Determine appropriate error response
      const isTokenError = error.message?.includes('JWT') || 
                          error.message?.includes('token') ||
                          error.message?.includes('signature')
      
      return jsonResponse(
        {
          error: isTokenError ? 'Invalid token' : 'Verification failed',
          details: env.ENVIRONMENT === 'development' ? error.message : undefined
        },
        isTokenError ? 401 : 500,
        corsHeaders
      )
    }
  },
}

/**
 * Rate Limiter Durable Object
 */
export class RateLimiter {
  state: DurableObjectState
  env: Env

  constructor(state: DurableObjectState, env: Env) {
    this.state = state
    this.env = env
  }

  async fetch(request: Request): Promise<Response> {
    const { key, limit, window } = await request.json() as {
      key: string
      limit: number
      window: number
    }

    const now = Date.now()
    const windowStart = now - (window * 1000)

    // Get current count
    const countKey = `count:${key}`
    const requests = await this.state.storage.get<number[]>(countKey) || []
    
    // Filter out old requests
    const validRequests = requests.filter(timestamp => timestamp > windowStart)
    
    // Check if limit exceeded
    if (validRequests.length >= limit) {
      const oldestRequest = Math.min(...validRequests)
      const resetTime = oldestRequest + (window * 1000)
      
      return new Response('Rate limit exceeded', {
        status: 429,
        headers: {
          'X-RateLimit-Limit': limit.toString(),
          'X-RateLimit-Remaining': '0',
          'X-RateLimit-Reset': new Date(resetTime).toISOString()
        }
      })
    }

    // Add current request
    validRequests.push(now)
    await this.state.storage.put(countKey, validRequests)

    // Set alarm to clean up old data
    await this.state.storage.setAlarm(now + (window * 1000))

    return new Response('OK', {
      headers: {
        'X-RateLimit-Limit': limit.toString(),
        'X-RateLimit-Remaining': (limit - validRequests.length).toString(),
        'X-RateLimit-Reset': new Date(now + (window * 1000)).toISOString()
      }
    })
  }

  async alarm() {
    // Clean up old rate limit data
    const now = Date.now()
    const storage = await this.state.storage.list()
    
    for (const [key, value] of storage) {
      if (key.startsWith('count:')) {
        const requests = value as number[]
        const validRequests = requests.filter(timestamp => timestamp > now - 3600000) // Keep last hour
        
        if (validRequests.length === 0) {
          await this.state.storage.delete(key)
        } else {
          await this.state.storage.put(key, validRequests)
        }
      }
    }
  }
}

/**
 * Helper function to create JSON responses
 */
function jsonResponse(
  data: any,
  status: number = 200,
  headers: Record<string, string> = {}
): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...headers
    }
  })
}