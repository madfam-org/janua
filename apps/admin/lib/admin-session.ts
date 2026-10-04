import { createRemoteJWKSet, jwtVerify } from 'jose'
import type { User } from '@janua/typescript-sdk'

export class AdminSessionError extends Error {
  constructor(public readonly status: 401 | 403 | 503) {
    super(status === 403 ? 'Admin access required' : status === 503 ? 'Authentication unavailable' : 'Invalid session')
  }
}

// Preserve the complete upstream profile, while requiring only fields used by
// this gate. /auth/me's schema is smaller than the general SDK User model.
export interface AdminSessionUser extends Partial<User> {
  id: string
  email: string
  is_admin: true
}

let jwks: ReturnType<typeof createRemoteJWKSet> | undefined
let jwksSource = ''
let discovery: { source: string; issuer: string; jwksUri: string; expiresAt: number } | undefined
let pendingDiscovery: { source: string; result: Promise<{ issuer: string; jwksUri: string }> } | undefined

function trustedMetadataUrl(value: unknown): string {
  if (typeof value !== 'string') throw new AdminSessionError(503)
  const url = new URL(value)
  if (url.protocol !== 'https:' && !(process.env.NODE_ENV !== 'production' && url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
    throw new AdminSessionError(503)
  }
  if (url.username || url.password) throw new AdminSessionError(503)
  return value
}

async function signingMetadata(publicApi: string): Promise<{ issuer: string; jwksUri: string }> {
  if (process.env.JANUA_ISSUER) {
    const issuer = process.env.JANUA_ISSUER
    return { issuer, jwksUri: process.env.JANUA_JWKS_URL || `${issuer.replace(/\/$/, '')}/.well-known/jwks.json` }
  }
  if (discovery?.source === publicApi && discovery.expiresAt > Date.now()) return discovery
  if (pendingDiscovery?.source === publicApi) return pendingDiscovery.result
  // Trust only the configured API origin. Hosted Janua serves api.janua.dev
  // while its canonical issuer is auth.madfam.io; the token itself must never
  // select the discovery URL. Revalidate metadata every five minutes.
  const result = (async () => {
    try {
      const response = await fetch(`${publicApi}/.well-known/openid-configuration`, {
        cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000),
      })
      if (!response.ok) throw new AdminSessionError(503)
      const metadata = await response.json()
      const issuer = trustedMetadataUrl(metadata.issuer)
      const jwksUri = trustedMetadataUrl(process.env.JANUA_JWKS_URL || metadata.jwks_uri)
      discovery = { source: publicApi, issuer, jwksUri, expiresAt: Date.now() + 300_000 }
      return { issuer, jwksUri }
    } catch {
      throw new AdminSessionError(503)
    }
  })()
  pendingDiscovery = { source: publicApi, result }
  try {
    return await result
  } finally {
    if (pendingDiscovery?.result === result) pendingDiscovery = undefined
  }
}

/** Shared by the edge gate and cookie bridge; never trust identity cookies. */
export async function verifyAdminSession(token: string): Promise<{ user: AdminSessionUser; expiresAt: number }> {
  const publicApi = (process.env.NEXT_PUBLIC_JANUA_API_URL || process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev').replace(/\/$/, '')
  const { issuer, jwksUri: source } = await signingMetadata(publicApi)
  const audience = process.env.JANUA_ADMIN_AUDIENCE || process.env.NEXT_PUBLIC_JANUA_AUDIENCE || 'janua.dev'

  let subject: string
  let expiresAt: number
  try {
    if (!jwks || jwksSource !== source) {
      jwks = createRemoteJWKSet(new URL(source), { timeoutDuration: 5000 })
      jwksSource = source
    }
    const { payload } = await jwtVerify(token, jwks, {
      algorithms: ['RS256'],
      issuer,
      audience,
      requiredClaims: ['sub', 'exp', 'iss', 'aud'],
      clockTolerance: 30,
    })
    // ID, refresh, MFA and machine tokens must never open a human console.
    if (payload.type !== 'access' || !payload.sub || payload.sub.startsWith('service-account:') || payload.is_service_account === true || typeof payload.exp !== 'number' || payload.exp <= Date.now() / 1000) {
      throw new AdminSessionError(401)
    }
    subject = payload.sub
    expiresAt = payload.exp
  } catch {
    throw new AdminSessionError(401)
  }

  // Password-session tokens omit platform roles; OIDC roles include org roles.
  // /auth/me verifies the token and loads the ACTIVE user from the database.
  // Its is_admin flag is the same authority used by the admin API, and reflects
  // removal of operator access even while a signed token is still unexpired.
  const api = (process.env.INTERNAL_API_URL || publicApi).replace(/\/$/, '')
  let response: Response
  let user: AdminSessionUser
  try {
    response = await fetch(`${api}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) {
      throw new AdminSessionError(response.status === 401 || response.status === 403 ? 401 : 503)
    }
    user = await response.json()
  } catch (error) {
    throw error instanceof AdminSessionError ? error : new AdminSessionError(503)
  }
  if (!user || user.id !== subject || typeof user.email !== 'string') {
    throw new AdminSessionError(401)
  }
  const allowedDomains = (process.env.ALLOWED_ADMIN_DOMAINS || '@janua.dev,@madfam.io')
    .split(',').map(domain => domain.trim().toLowerCase()).filter(Boolean)
  const domain = user.email.slice(user.email.lastIndexOf('@')).toLowerCase()
  if (user.is_admin !== true || !allowedDomains.includes(domain)) {
    throw new AdminSessionError(403)
  }
  return { user, expiresAt }
}
