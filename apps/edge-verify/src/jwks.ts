/**
 * JWKS caching utilities
 */

import { JWKS } from './jwt'

export class JWKSCache {
  constructor(private kv: KVNamespace) {}

  /**
   * Get JWKS with caching
   */
  async get(url: string): Promise<JWKS | null> {
    const cacheKey = `jwks:${url}`
    
    // Try to get from cache
    const cached = await this.kv.get(cacheKey, 'json')
    if (cached) {
      return cached as JWKS
    }

    // Fetch from URL
    try {
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'Plinto-Edge-Verify/1.0'
        }
      })

      if (!response.ok) {
        console.error(`Failed to fetch JWKS: ${response.status}`)
        return null
      }

      const jwks = await response.json() as JWKS

      // Validate JWKS structure
      if (!jwks.keys || !Array.isArray(jwks.keys)) {
        console.error('Invalid JWKS structure')
        return null
      }

      // Cache for 5 minutes
      await this.kv.put(
        cacheKey,
        JSON.stringify(jwks),
        {
          expirationTtl: 300, // 5 minutes
          metadata: {
            fetchedAt: new Date().toISOString(),
            url
          }
        }
      )

      return jwks
    } catch (error) {
      console.error('Error fetching JWKS:', error)
      return null
    }
  }

  /**
   * Invalidate JWKS cache
   */
  async invalidate(url: string): Promise<void> {
    const cacheKey = `jwks:${url}`
    await this.kv.delete(cacheKey)
  }
}

/**
 * Get JWKS from URL with retries
 */
export async function getJWKS(
  url: string,
  maxRetries: number = 3
): Promise<JWKS | null> {
  let lastError: Error | null = null

  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'Plinto-Edge-Verify/1.0'
        }
      })

      if (response.ok) {
        const jwks = await response.json() as JWKS
        
        // Validate JWKS
        if (jwks.keys && Array.isArray(jwks.keys) && jwks.keys.length > 0) {
          return jwks
        }
      }

      lastError = new Error(`HTTP ${response.status}: ${response.statusText}`)
    } catch (error) {
      lastError = error as Error
    }

    // Exponential backoff
    if (i < maxRetries - 1) {
      await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 100))
    }
  }

  console.error('Failed to fetch JWKS after retries:', lastError)
  return null
}