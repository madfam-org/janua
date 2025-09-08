import * as jose from 'jose'
import type { JWKS, JWTPayload } from './types'

export interface VerifyOptions {
  audience?: string | string[]
  issuer?: string
  clockTolerance?: number
}

export async function verifyToken(
  token: string, 
  jwks: JWKS, 
  options: VerifyOptions = {}
): Promise<JWTPayload> {
  const { 
    audience = 'plinto.dev', 
    issuer = 'https://plinto.dev',
    clockTolerance = 30
  } = options

  // Parse JWT header to get kid
  const { kid } = jose.decodeProtectedHeader(token)
  if (!kid) {
    throw new Error('JWT missing kid in header')
  }

  // Find matching JWK
  const jwk = jwks.keys.find(key => key.kid === kid)
  if (!jwk) {
    throw new Error(`JWK not found for kid: ${kid}`)
  }

  // Import public key
  const publicKey = await jose.importJWK(jwk)

  // Verify JWT
  const { payload } = await jose.jwtVerify(token, publicKey, {
    audience,
    issuer,
    clockTolerance
  })

  return payload as JWTPayload
}

export { type JWTPayload }