import { createRemoteJWKSet, jwtVerify } from 'jose'
import type { User } from '@janua/typescript-sdk'
import { readConsoleConfig, readConsoleApi } from './console-runtime.server'

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
/** Shared by the edge gate and cookie bridge; never trust identity cookies. */
export async function verifyAdminSession(token: string): Promise<{ user: AdminSessionUser; expiresAt: number }> {
  let runtime
  let api: string
  try { runtime = readConsoleConfig(); api = readConsoleApi() } catch { throw new AdminSessionError(503) }
  const { issuer, audience } = runtime
  const source = runtime.environment === 'staging' ? `${api}/.well-known/jwks.json` : runtime.jwksUri

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
  let response: Response
  let user: AdminSessionUser
  try {
    response = await fetch(`${api}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
      credentials: 'omit',
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
