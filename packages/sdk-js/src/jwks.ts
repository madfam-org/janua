import type { JWKS } from './types'

export class JWKSCache {
  private jwksUrl: string
  private cache: JWKS | null = null
  private cacheExpiry: number = 0
  private readonly cacheDuration = 24 * 60 * 60 * 1000 // 24 hours

  constructor(jwksUrl: string) {
    this.jwksUrl = jwksUrl
  }

  async get(): Promise<JWKS | null> {
    const now = Date.now()
    
    // Return cached JWKS if still valid
    if (this.cache && now < this.cacheExpiry) {
      return this.cache
    }

    try {
      // Fetch fresh JWKS
      const response = await fetch(this.jwksUrl)
      if (!response.ok) {
        throw new Error(`Failed to fetch JWKS: ${response.status} ${response.statusText}`)
      }

      const jwks = await response.json() as JWKS
      
      // Validate JWKS structure
      if (!jwks.keys || !Array.isArray(jwks.keys)) {
        throw new Error('Invalid JWKS format: missing keys array')
      }

      // Cache the JWKS
      this.cache = jwks
      this.cacheExpiry = now + this.cacheDuration

      return jwks
    } catch (error) {
      console.error('Failed to fetch JWKS:', error)
      // Return stale cache if available
      return this.cache
    }
  }

  clear(): void {
    this.cache = null
    this.cacheExpiry = 0
  }
}