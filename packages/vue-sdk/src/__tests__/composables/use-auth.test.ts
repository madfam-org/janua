import { describe, it, expect, vi } from 'vitest'
import { useAuth } from '../../composables'
import { withSetup } from '../helpers'

vi.mock('@janua/typescript-sdk', () => ({
  JanuaClient: vi.fn().mockImplementation(() => ({
    auth: {
      signIn: vi.fn().mockResolvedValue({ access_token: 'tok' }),
      signUp: vi.fn().mockResolvedValue({ id: '1' }),
      signOut: vi.fn().mockResolvedValue(undefined),
      getCurrentUser: vi.fn().mockResolvedValue(null),
      handleOAuthCallback: vi.fn(),
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
  })),
  checkWebAuthnSupport: vi.fn().mockReturnValue({ available: true, platform: false, conditional: false }),
}))

describe('useAuth', () => {
  it('returns reactive user, session, isLoading, isAuthenticated, error', () => {
    const { result } = withSetup(() => useAuth())

    expect(result.user.value).toBeNull()
    expect(result.session.value).toBeNull()
    expect(result.isAuthenticated.value).toBe(false)
    expect(result.isLoading.value).toBeDefined()
    expect(result.error.value).toBeNull()
  })

  it('exposes signIn, signUp, signOut as functions', () => {
    const { result } = withSetup(() => useAuth())

    expect(typeof result.signIn).toBe('function')
    expect(typeof result.signUp).toBe('function')
    expect(typeof result.signOut).toBe('function')
  })

  it('signIn delegates to JanuaVue.signIn', async () => {
    const { result } = withSetup(() => useAuth())

    // signIn should not throw with mocked client
    await expect(result.signIn('a@b.com', 'pass')).resolves.toBeDefined()
  })

  it('error computed reflects plugin state error after failed signIn', async () => {
    const { result } = withSetup(() => useAuth())

    // Force signIn to reject on the underlying auth mock
    const { JanuaClient } = await import('@janua/typescript-sdk')
    const instance = new JanuaClient({} as any)
    ;(instance.auth.signIn as any).mockRejectedValueOnce(new Error('fail'))

    try {
      await result.signIn('a@b.com', 'bad')
    } catch {
      // expected
    }

    expect(result.error.value).toBeTruthy()
  })
})
