/**
 * JWT verification utilities
 */

export interface JWTPayload {
  sub: string  // Subject (identity ID)
  tid: string  // Tenant ID
  oid?: string // Organization ID
  iat: number  // Issued at
  exp: number  // Expiration
  nbf?: number // Not before
  jti: string  // JWT ID
  iss: string  // Issuer
  aud: string | string[] // Audience
  type: string // Token type
  [key: string]: any
}

export interface JWK {
  kty: string
  use?: string
  kid: string
  alg: string
  n: string
  e: string
}

export interface JWKS {
  keys: JWK[]
}

export interface VerifyOptions {
  audience?: string | string[]
  issuer?: string
  clockTolerance?: number
}

/**
 * Verify JWT token using JWKS
 */
export async function verifyJWT(
  token: string,
  jwks: JWKS,
  options: VerifyOptions = {}
): Promise<JWTPayload> {
  // Parse JWT
  const parts = token.split('.')
  if (parts.length !== 3) {
    throw new Error('Invalid JWT format')
  }

  const [headerB64, payloadB64, signatureB64] = parts

  // Decode header
  const header = JSON.parse(atob(headerB64.replace(/-/g, '+').replace(/_/g, '/')))
  
  // Find matching key
  const key = jwks.keys.find(k => k.kid === header.kid)
  if (!key) {
    throw new Error(`No matching key found for kid: ${header.kid}`)
  }

  // Import the public key
  const publicKey = await importPublicKey(key)

  // Verify signature
  const encoder = new TextEncoder()
  const data = encoder.encode(`${headerB64}.${payloadB64}`)
  const signature = base64UrlDecode(signatureB64)

  const valid = await crypto.subtle.verify(
    {
      name: 'RSASSA-PKCS1-v1_5',
      hash: 'SHA-256'
    },
    publicKey,
    signature,
    data
  )

  if (!valid) {
    throw new Error('Invalid JWT signature')
  }

  // Decode and validate payload
  const payload = JSON.parse(
    atob(payloadB64.replace(/-/g, '+').replace(/_/g, '/'))
  ) as JWTPayload

  // Validate claims
  const now = Math.floor(Date.now() / 1000)
  const clockTolerance = options.clockTolerance || 0

  // Check expiration
  if (payload.exp && now > payload.exp + clockTolerance) {
    throw new Error('JWT has expired')
  }

  // Check not before
  if (payload.nbf && now < payload.nbf - clockTolerance) {
    throw new Error('JWT not yet valid')
  }

  // Check audience
  if (options.audience) {
    const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud]
    const expectedAudiences = Array.isArray(options.audience) 
      ? options.audience 
      : [options.audience]
    
    const hasValidAudience = expectedAudiences.some(expected => 
      audiences.includes(expected)
    )
    
    if (!hasValidAudience) {
      throw new Error('Invalid JWT audience')
    }
  }

  // Check issuer
  if (options.issuer && payload.iss !== options.issuer) {
    throw new Error('Invalid JWT issuer')
  }

  return payload
}

/**
 * Import JWK as CryptoKey
 */
async function importPublicKey(jwk: JWK): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'jwk',
    {
      kty: jwk.kty,
      n: jwk.n,
      e: jwk.e,
      alg: jwk.alg,
      use: 'sig'
    },
    {
      name: 'RSASSA-PKCS1-v1_5',
      hash: 'SHA-256'
    },
    false,
    ['verify']
  )
}

/**
 * Decode base64url string to Uint8Array
 */
function base64UrlDecode(str: string): Uint8Array {
  // Add padding if necessary
  const padding = '='.repeat((4 - str.length % 4) % 4)
  const base64 = (str + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/')

  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  
  return bytes
}