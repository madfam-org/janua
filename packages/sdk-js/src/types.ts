export interface PlintoConfig {
  apiKey?: string
  tenantId?: string
  baseUrl?: string
  audience?: string
  issuer?: string
  jwksUrl?: string
  enableLocalVerification?: boolean
}

export interface CreateIdentityData {
  email: string
  password?: string
  profile?: Record<string, any>
  metadata?: Record<string, any>
}

export interface CreateSessionData {
  email: string
  password: string
  remember?: boolean
}

export interface Identity {
  id: string
  email: string
  email_verified: boolean
  profile: Record<string, any>
  metadata: Record<string, any>
  status: string
  created_at: string
  updated_at: string
  last_sign_in_at?: string
}

export interface Session {
  id: string
  identity_id: string
  access_token?: string
  refresh_token?: string
  expires_at: string
  created_at: string
  last_activity_at: string
}

export interface Organization {
  id: string
  slug: string
  name: string
  description?: string
  settings: Record<string, any>
  created_at: string
  updated_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token?: string
  expires_in: number
  token_type: string
}

export interface PlintoError {
  code: string
  message: string
  status?: number
}

export interface JWTPayload {
  sub: string
  aud: string | string[]
  iss: string
  exp: number
  iat: number
  jti?: string
  tenant_id?: string
  identity_id?: string
  session_id?: string
  scope?: string
  permissions?: string[]
}

export interface JWK {
  kty: string
  use?: string
  key_ops?: string[]
  alg?: string
  kid: string
  n?: string
  e?: string
  x?: string
  y?: string
  crv?: string
  d?: string
}

export interface JWKS {
  keys: JWK[]
}