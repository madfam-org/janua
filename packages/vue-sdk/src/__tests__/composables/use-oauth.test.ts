import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useOAuth } from '../../composables'
import { withSetup } from '../helpers'

vi.mock('@janua/typescript-sdk', () => ({
  JanuaClient: vi.fn().mockImplementation(() => ({
    auth: {
      signIn: vi.fn(),
      signUp: vi.fn(),
      signOut: vi.fn(),
      getCurrentUser: vi.fn().mockResolvedValue(null),
      handleOAuthCallback: vi.fn().mockResolvedValue(undefined),
      sendMagicLink: vi.fn(),
      verifyMagicLink: vi.fn(),
      enableMFA: vi.fn(),
      verifyMFA: vi.fn(),
      disableMFA: vi.fn(),
    },
    users: { updateCurrentUser: vi.fn() },
    organizations: {},
    getCurrentUser: vi.fn().mockResolvedValue(null),
    getAccessToken: vi.fn().mockResolvedValue(null),
    getRefreshToken: vi.fn().mockResolvedValue(null),
    signOut: vi.fn().mockResolvedValue(undefined),
    signInWithPasskey: vi.fn(),
    registerPasskey: vi.fn(),
    config: { baseURL: 'http://localhost:4100' },
  })),
  checkWebAuthnSupport: vi.fn().mockReturnValue({ available: true, platform: false, conditional: false }),
  generateCodeVerifier: vi.fn().mockReturnValue('test-verifier'),
  generateCodeChallenge: vi.fn().mockResolvedValue('test-challenge'),
  generateState: vi.fn().mockReturnValue('test-state'),
  storePKCEParams: vi.fn(),
  retrievePKCEParams: vi.fn().mockReturnValue({ codeVerifier: 'test-verifier', state: 'test-state' }),
  clearPKCEParams: vi.fn(),
  validateState: vi.fn().mockReturnValue(true),
  buildAuthorizationUrl: vi.fn().mockReturnValue('http://localhost:4100/oauth/authorize?test=1'),
}))

describe('useOAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Prevent actual navigation
    Object.defineProperty(window, 'location', {
      value: { href: '', origin: 'http://localhost', pathname: '/', search: '' },
      writable: true,
    })
    window.history.replaceState = vi.fn()
  })

  it('signInWithOAuth generates PKCE params and redirects', async () => {
    const { result } = withSetup(() => useOAuth())
    const { storePKCEParams } = await import('@janua/typescript-sdk')

    await result.signInWithOAuth('google')

    expect(storePKCEParams).toHaveBeenCalled()
    expect(window.location.href).toContain('oauth/authorize')
  })

  it('handleOAuthCallback validates state and updates session', async () => {
    const { result } = withSetup(() => useOAuth())
    const { validateState, clearPKCEParams } = await import('@janua/typescript-sdk')

    await result.handleOAuthCallback('auth-code', 'test-state')

    expect(validateState).toHaveBeenCalledWith('test-state')
    expect(clearPKCEParams).toHaveBeenCalled()
  })

  it('handleOAuthCallback throws on invalid state', async () => {
    const { validateState } = await import('@janua/typescript-sdk')
    ;(validateState as any).mockReturnValueOnce(false)

    const { result } = withSetup(() => useOAuth())

    await expect(result.handleOAuthCallback('code', 'bad-state')).rejects.toThrow('Invalid OAuth state')
  })

  it('handleOAuthCallback throws on missing PKCE params', async () => {
    const { retrievePKCEParams } = await import('@janua/typescript-sdk')
    ;(retrievePKCEParams as any).mockReturnValueOnce(null)

    const { result } = withSetup(() => useOAuth())

    await expect(result.handleOAuthCallback('code', 'test-state')).rejects.toThrow('Missing PKCE parameters')
  })
})
