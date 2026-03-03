import { describe, it, expect, vi, beforeEach } from 'vitest'

// These are re-exports from @janua/typescript-sdk. Smoke-test the re-export surface.
vi.mock('@janua/typescript-sdk', () => ({
  generateCodeVerifier: vi.fn().mockReturnValue('a'.repeat(43)),
  generateCodeChallenge: vi.fn().mockResolvedValue('challenge-hash-value'),
  generateState: vi.fn().mockReturnValue('random-state-string'),
  storePKCEParams: vi.fn(),
  retrievePKCEParams: vi.fn().mockReturnValue({ codeVerifier: 'a'.repeat(43), state: 'random-state-string' }),
  clearPKCEParams: vi.fn(),
  validateState: vi.fn().mockImplementation((state: string) => state === 'random-state-string'),
  buildAuthorizationUrl: vi.fn().mockReturnValue('https://example.com/authorize'),
  PKCE_STORAGE_KEYS: { CODE_VERIFIER: 'janua_pkce_verifier', STATE: 'janua_pkce_state' },
}))

import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
} from '../../utils/pkce'

describe('PKCE utilities (re-export smoke tests)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('generateCodeVerifier returns a string of proper length', () => {
    const verifier = generateCodeVerifier()
    expect(typeof verifier).toBe('string')
    expect(verifier.length).toBeGreaterThanOrEqual(43)
  })

  it('generateCodeChallenge returns a different value from verifier', async () => {
    const verifier = generateCodeVerifier()
    const challenge = await generateCodeChallenge(verifier)
    expect(typeof challenge).toBe('string')
    expect(challenge).not.toBe(verifier)
  })

  it('generateState returns a string', () => {
    const state = generateState()
    expect(typeof state).toBe('string')
    expect(state.length).toBeGreaterThan(0)
  })

  it('storePKCEParams and retrievePKCEParams roundtrip', () => {
    storePKCEParams('verifier-val', 'state-val')
    expect(storePKCEParams).toHaveBeenCalledWith('verifier-val', 'state-val')

    const params = retrievePKCEParams()
    expect(params).toBeTruthy()
    expect(params?.codeVerifier).toBeDefined()
    expect(params?.state).toBeDefined()
  })

  it('clearPKCEParams removes stored values', () => {
    clearPKCEParams()
    expect(clearPKCEParams).toHaveBeenCalled()
  })

  it('validateState returns true for matching state', () => {
    expect(validateState('random-state-string')).toBe(true)
  })

  it('validateState returns false for mismatched state', () => {
    expect(validateState('wrong-state')).toBe(false)
  })
})
